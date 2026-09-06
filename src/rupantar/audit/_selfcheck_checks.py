"""Static selfcheck probes: Python, media tools, model files, ports, renderers, converters."""

from __future__ import annotations

import platform
import shutil
import socket
import subprocess  # noqa: S404 - version probing of media CLIs only; see tests/inv exemption
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import psutil

from rupantar.audit._fixtures import sample_artefacts, write_converter_samples
from rupantar.audit.egress import scan_egress
from rupantar.models.registry import ModelEntry, Registry, _sha256

if TYPE_CHECKING:
    from rupantar.audit.selfcheck import CheckResult
    from rupantar.core.config import AppConfig


def _result(number: str, name: str, level: str, detail: str, **data: object) -> CheckResult:
    """Build a CheckResult without importing selfcheck at module scope."""
    from rupantar.audit.selfcheck import CheckResult

    return CheckResult(number=number, name=name, level=level, detail=detail, data=data)


def check_python() -> list[CheckResult]:
    """Check 1: Python is exactly 3.11, plus platform and free RAM/disk."""
    major_minor = sys.version_info[:2]
    ok = major_minor == (3, 11)
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(str(Path.cwd()))
    detail = (
        f"Python {platform.python_version()} on {platform.system()}/{platform.machine()}; "
        f"RAM free {vm.available / 1e9:.1f} GB / {vm.total / 1e9:.1f} GB; "
        f"disk free {disk.free / 1e9:.1f} GB"
    )
    if not ok:
        detail = f"Python {platform.python_version()} is not 3.11 — recreate the venv with 3.11"
    return [
        _result(
            "1",
            "python + platform",
            "ok" if ok else "fail",
            detail,
            python=platform.python_version(),
            platform=f"{platform.system()}/{platform.machine()}",
            ram_free_gb=round(vm.available / 1e9, 1),
            disk_free_gb=round(disk.free / 1e9, 1),
        )
    ]


def _tool_version(argv: list[str]) -> str:
    """First line of `argv --version`-style output, or '?' when it cannot be read."""
    try:
        out = subprocess.run(  # noqa: S603
            argv, capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return "?"
    text = (out.stdout or out.stderr or "").strip().splitlines()
    return text[0][:80] if text else "?"


def _piper_probe() -> tuple[bool, str]:
    """Resolve piper as a console script or as `python -m piper`."""
    if shutil.which("piper"):
        return True, _tool_version(["piper", "--version"])
    version = _tool_version([sys.executable, "-m", "piper", "--version"])
    return version != "?", version


def check_tools() -> list[CheckResult]:
    """Check 2: ffmpeg, llama-server, and piper are on PATH with a readable version."""
    results: list[CheckResult] = []
    for name, argv in (
        ("ffmpeg", ["ffmpeg", "-version"]),
        ("llama-server", ["llama-server", "--version"]),
    ):
        found = shutil.which(name) is not None
        version = _tool_version(argv) if found else "not on PATH"
        results.append(
            _result(
                "2",
                f"tool: {name}",
                "ok" if found else "fail",
                f"{version}" if found else f"{name} not found — install it and re-run",
                path=shutil.which(name),
                version=version,
            )
        )
    piper_ok, piper_version = _piper_probe()
    results.append(
        _result(
            "2",
            "tool: piper",
            "ok" if piper_ok else "fail",
            piper_version if piper_ok else "piper not runnable — pip install piper-tts",
            version=piper_version,
        )
    )
    return results


def _hash_matches(path: Path, declared: str | None) -> tuple[str, str]:
    """Return (level, detail) comparing the on-disk SHA-256 of `path` with `declared`."""
    if declared is None:
        return "ok", f"{path.name}: present ({path.stat().st_size} B), no SHA declared"
    actual = _sha256(path)
    if actual.lower() == declared.lower():
        return "ok", f"{path.name}: SHA-256 ok ({path.stat().st_size} B)"
    return (
        "fail",
        f"{path.name}: SHA-256 mismatch (got {actual[:12]}…, want {declared[:12]}…) — "
        "re-run scripts/fetch_models.sh",
    )


def _check_one_model(entry: ModelEntry, *, fast: bool) -> CheckResult:
    """Check one profile model's file(s) exist and (unless fast) hash to the declared value."""
    if entry.is_stub:
        return _result("3", f"model: {entry.key}", "ok", "stub runtime — no file to verify")
    if entry.path is None or not entry.path.exists():
        return _result(
            "3",
            f"model: {entry.key}",
            "fail",
            f"{entry.path} missing — run scripts/fetch_models.sh while online",
        )
    targets: list[tuple[Path, str | None]] = []
    if entry.path.is_dir():
        targets.append((entry.path / "model.bin", entry.extra.get("model_bin_sha256")))
    else:
        targets.append((entry.path, entry.declared_sha256 or entry.extra.get("model_bin_sha256")))
        for sib_key, sha_key in (("mmproj", "mmproj_sha256"), ("config", None)):
            sib = entry.extra.get(sib_key)
            if sib:
                targets.append((Path(sib), entry.extra.get(sha_key) if sha_key else None))
    levels: list[str] = []
    details: list[str] = []
    for target, declared in targets:
        if not target.exists():
            levels.append("fail")
            details.append(f"{target} missing — run scripts/fetch_models.sh")
            continue
        if fast:
            levels.append("ok")
            details.append(f"{target.name}: present ({target.stat().st_size} B)")
            continue
        level, detail = _hash_matches(target, declared)
        levels.append(level)
        details.append(detail)
    worst = "fail" if "fail" in levels else ("warn" if "warn" in levels else "ok")
    return _result("3", f"model: {entry.key}", worst, "; ".join(details))


def check_model_files(config: AppConfig, *, fast: bool) -> list[CheckResult]:
    """Check 3: every model file in the active profile exists and matches models.yaml."""
    registry = Registry.from_config(config, verify=False)
    return [_check_one_model(registry.entry(key), fast=fast) for key in registry.key_list()]


def check_ports(config: AppConfig) -> list[CheckResult]:
    """Check 4: TCP ports in policy.port_range bind on 127.0.0.1."""
    low, high = config.policy.get("port_range", [8100, 8199])
    free = 0
    in_use: list[int] = []
    for port in range(int(low), int(high) + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                free += 1
            except OSError:
                in_use.append(port)
    total = int(high) - int(low) + 1
    level = "fail" if free == 0 else ("warn" if free < 5 else "ok")
    return [
        _result(
            "4",
            "ports free",
            level,
            f"{free}/{total} ports free in {low}-{high}"
            + (f"; in use: {in_use[:10]}" if in_use else ""),
            free=free,
            total=total,
            in_use=in_use,
        )
    ]


def check_renderers() -> list[CheckResult]:
    """Check 6: every renderer produces a non-empty sample file."""
    from rupantar.render.base import FORMATS, render

    results: list[CheckResult] = []
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for atype, artefact in sample_artefacts().items():
            out = tmp / atype
            try:
                paths = render(artefact, out, formats=FORMATS.get(atype))
                bad = [p for p in paths if not (p.is_file() and p.stat().st_size > 0)]
                level = "fail" if bad else "ok"
                detail = f"{len(paths)} file(s): {sorted(p.suffix.lstrip('.') for p in paths)}"
                if bad:
                    detail = f"empty output: {[p.name for p in bad]}"
            except Exception as exc:  # noqa: BLE001 - a health check reports, never crashes
                level, detail = "fail", f"render raised {type(exc).__name__}: {exc}"
            results.append(_result("6", f"render: {atype}", level, detail))
    return results


_ROUND_TRIPS: tuple[tuple[str, str, str, str], ...] = (
    ("csv", "csv", "json", "csv"),
    ("ioc-csv", "ioc-csv", "stix21", "ioc-csv"),
    ("sigma", "sigma", "sigma-json", ""),
    ("cef", "cef", "jsonl", ""),
)


def check_converters() -> list[CheckResult]:
    """Check 7: representative converters round-trip a synthetic fixture."""
    from rupantar.parivartan.registry import convert

    results: list[CheckResult] = []
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        samples = write_converter_samples(tmp / "in")
        for name, src, mid, back in _ROUND_TRIPS:
            try:
                first = convert(samples[name], src, mid, tmp / f"{name}.{mid}")
                level = "ok" if first.ok else "fail"
                detail = f"{src}->{mid}: {first.rows} rows"
                if back:
                    second = convert(Path(first.output_path or ""), mid, back, tmp / f"{name}.back")
                    level = "ok" if first.ok and second.ok else "fail"
                    detail += f", {mid}->{back}: {second.rows} rows"
            except Exception as exc:  # noqa: BLE001 - a health check reports, never crashes
                level, detail = "fail", f"convert raised {type(exc).__name__}: {exc}"
            results.append(_result("7", f"convert: {name}", level, detail))
    return results


def check_egress_now(baseline_clean: bool) -> list[CheckResult]:
    """Check 8: no non-loopback connection during the selfcheck run."""
    report = scan_egress()
    clean = report.clean and baseline_clean
    detail = (
        f"{len(report.scanned_pids)} process(es) scanned, no non-loopback remote"
        if clean
        else f"non-loopback connections: {[v.raddr for v in report.violations]}"
    )
    return [_result("8", "egress during run", "ok" if clean else "fail", detail)]
