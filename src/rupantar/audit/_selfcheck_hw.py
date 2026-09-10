"""Live selfcheck probes: hardware/profile/offload consistency (4b) and the Model Manager (5)."""

from __future__ import annotations

import platform
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import psutil

from rupantar.models.client import LlamaClient
from rupantar.models.manager import ModelManager
from rupantar.models.registry import ModelEntry, Registry
from rupantar.models.runtime_base import Runtime

if TYPE_CHECKING:
    from rupantar.audit.selfcheck import CheckResult
    from rupantar.core.config import AppConfig

_GPU_PROFILES = {"apple-metal", "nvidia-cuda"}
_MAX_AGENT_TOKENS = 2600  # largest configs/agents/*.yaml max_tokens (presentation, video_package)
_RSS_TOLERANCE = 200_000_000


def _result(number: str, name: str, level: str, detail: str, **data: object) -> CheckResult:
    """Build a CheckResult without importing selfcheck at module scope."""
    from rupantar.audit.selfcheck import CheckResult

    return CheckResult(number=number, name=name, level=level, detail=detail, data=data)


def _brain_args(config: AppConfig) -> list[str]:
    """The resolved llama-server args for the active profile's brain entry."""
    spec = config.profile_models.get("brain", {})
    args = spec.get("args", [])
    return [str(a) for a in args] if isinstance(args, list) else []


def _flag_value(args: list[str], flag: str) -> str | None:
    """Value following `flag` in an argv list, or None."""
    return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else None


def _arg_warnings(args: list[str]) -> list[str]:
    """Static warnings about --parallel and ctx/parallel vs the largest agent max_tokens."""
    warnings: list[str] = []
    if "--parallel" not in args:
        warnings.append("--parallel is unset — llama-server auto-splits ctx across 4 slots")
    ctx = int(_flag_value(args, "--ctx-size") or 0)
    parallel = int(_flag_value(args, "--parallel") or 1)
    if ctx and parallel and ctx // parallel < _MAX_AGENT_TOKENS:
        warnings.append(
            f"ctx-size/parallel = {ctx // parallel} < largest agent max_tokens "
            f"({_MAX_AGENT_TOKENS}) — long artefacts may truncate"
        )
    return warnings


def _verbose_factory(config: AppConfig, log_dir: Path) -> Callable[[ModelEntry, int], Runtime]:
    """A runtime factory that boots the llama brain verbosely and captures its log."""
    from rupantar.models._support import default_runtime_factory
    from rupantar.models.runtime_llama import LlamaRuntime

    registry = Registry.from_config(config, verify=False)
    fallback = default_runtime_factory(registry, config.policy)

    def _make(entry: ModelEntry, port: int) -> Runtime:
        if entry.key != "brain" or entry.is_stub or entry.runtime != "llama":
            return fallback(entry, port)
        llama = registry.runtime_spec("llama")
        # -v needs logging on; drop --log-disable so the offload line reaches the captured log.
        common = [str(a) for a in llama.get("common_args", []) if str(a) != "--log-disable"]
        return LlamaRuntime(
            entry=entry,
            port=port,
            binary=str(llama.get("binary", "llama-server")),
            host=str(llama.get("host", "127.0.0.1")),
            common_args=common,
            health_timeout=float(config.policy.get("health_timeout_seconds", 120)),
            verbose=True,
            log_path=log_dir / "brain-boot.log",
        )

    return _make


def _tree_rss() -> int:
    """Resident set size of this process plus every descendant, in bytes."""
    proc = psutil.Process()
    total = proc.memory_info().rss
    for child in proc.children(recursive=True):
        try:
            total += child.memory_info().rss
        except psutil.Error:
            continue
    return total


async def _one_token(endpoint: str) -> str:
    """Generate a single token against a leased model endpoint."""
    client = LlamaClient(endpoint)
    try:
        return await client.complete(
            [{"role": "user", "content": "ping"}], max_tokens=1, temperature=0.0
        )
    finally:
        await client.aclose()


def _static_4b(config: AppConfig) -> tuple[str, list[str], list[str]]:
    """Platform / profile / arg-hygiene portion of check 4b (no model load)."""
    args = _brain_args(config)
    warns = _arg_warnings(args)
    lines = [
        f"platform {platform.system()}/{platform.machine()}, "
        f"nvidia-smi {'present' if shutil.which('nvidia-smi') else 'absent'}",
        f"profile {config.active_profile} (source: {config.profile_source})",
    ]
    return config.active_profile, lines, warns


async def check_hw_offload(config: AppConfig, *, load_model: bool) -> list[CheckResult]:
    """Check 4b: platform/profile/offload consistency; fail if a GPU profile offloads 0 layers."""
    profile, lines, warns = _static_4b(config)
    level = "warn" if warns else "ok"
    detail_parts = [*lines, *(f"WARN: {w}" for w in warns)]
    registry = Registry.from_config(config, verify=False)
    if not load_model or registry.entry("brain").is_stub:
        detail_parts.append("offload check skipped (no model load / stub profile)")
        return [_result("4b", "hw / profile / offload", level, "; ".join(detail_parts))]

    with tempfile.TemporaryDirectory() as raw:
        manager = ModelManager(
            registry, policy=config.policy, runtime_factory=_verbose_factory(config, Path(raw))
        )
        try:
            async with manager.acquire("brain") as lease:
                await _one_token(lease.endpoint)
                probe = getattr(manager.runtime("brain"), "offloaded_layers", None)
                offload = probe() if callable(probe) else None
        finally:
            await manager.aclose()

    if offload is None:
        detail_parts.append("could not read offloaded layer count from the boot log")
        level = "warn"
    else:
        done, total = offload
        detail_parts.append(f"offloaded {done}/{total} layers to GPU")
        if profile in _GPU_PROFILES and done == 0:
            level = "fail"
            detail_parts.append(
                "GPU profile but 0 layers offloaded — llama.cpp built for the wrong backend "
                "(see README llama.cpp backend note)"
            )
        elif done > 0 and level != "fail":
            level = "ok" if not warns else "warn"
    return [_result("4b", "hw / profile / offload", level, "; ".join(detail_parts))]


async def check_model_manager(config: AppConfig, *, load_model: bool) -> list[CheckResult]:
    """Check 5: load brain, generate one token, unload, assert RSS returns to baseline ±200 MB."""
    registry = Registry.from_config(config, verify=False)
    if not load_model:
        # Honouring this is what makes the check safe to run inside a process that
        # already owns a ModelManager: building a second one here could put two heavy
        # models in memory at once (INV-2).
        return [
            _result(
                "5",
                "model manager load/unload",
                "ok",
                "load/unload check skipped (no model load requested)",
            )
        ]
    manager = ModelManager(registry, policy=config.policy)
    baseline = _tree_rss()
    try:
        async with manager.acquire("brain") as lease:
            await _one_token(lease.endpoint)
            resident = _tree_rss()
        await manager.evict("brain")
    except Exception as exc:  # noqa: BLE001 - a health check reports, never crashes
        await manager.aclose()
        return [_result("5", "model manager load/unload", "fail", f"{type(exc).__name__}: {exc}")]
    await manager.aclose()
    after = _tree_rss()
    drift = after - baseline
    level = "ok" if abs(drift) < _RSS_TOLERANCE else "fail"
    detail = (
        f"resident +{(resident - baseline) / 1e6:.0f} MB, "
        f"post-unload drift {drift / 1e6:+.0f} MB (tolerance ±200 MB)"
    )
    return [_result("5", "model manager load/unload", level, detail)]
