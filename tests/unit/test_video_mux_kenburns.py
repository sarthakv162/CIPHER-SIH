"""Unit coverage for the per-panel Ken Burns (zoompan) motion tier in render/_video_mux.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from rupantar.render import _video_mux as vm


class _Plan:
    """A minimal stand-in for `_video_scene.PanelPlan` (only the fields build_mp4 reads)."""

    def __init__(self, duration: int, narration: str = "narrated") -> None:
        self.duration = duration
        self.narration = narration


def _fake_success_run(argv: list[str], *, cwd: Path | None = None, **_kwargs: object) -> object:
    """A stand-in ffmpeg/ffprobe call: touches the ffmpeg target file, never raises."""
    if argv[0] == "ffmpeg" and "-filters" not in argv:
        (Path(cwd or ".") / argv[-1]).write_bytes(b"fake mp4 bytes")
    return type("R", (), {"returncode": 0, "stdout": ""})()


def _panels(tmp_path: Path, count: int) -> list[Path]:
    panels = []
    for i in range(count):
        p = tmp_path / f"panel_{i:02d}.png"
        p.write_bytes(b"\x89PNG\r\n")
        panels.append(p)
    return panels


def test_kenburns_tier_used_when_duration_checks_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(vm.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(vm, "_has_burn_in", lambda: False)
    monkeypatch.setattr(vm.subprocess, "run", _fake_success_run)
    monkeypatch.setattr(vm, "_duration_matches", lambda path, expected: True)

    plans = [_Plan(3), _Plan(4)]
    panels = _panels(tmp_path, 2)
    warnings: list[str] = []
    result = vm.build_mp4(tmp_path, plans, panels, None, warnings)

    assert result is not None and result.is_file()
    assert not any("degraded" in w for w in warnings)
    assert not any("Ken Burns" in w for w in warnings)


def test_kenburns_wrong_duration_falls_back_to_fade_xfade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(vm.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(vm, "_has_burn_in", lambda: False)
    monkeypatch.setattr(vm.subprocess, "run", _fake_success_run)
    monkeypatch.setattr(vm, "_duration_matches", lambda path, expected: False)

    plans = [_Plan(3), _Plan(4)]
    panels = _panels(tmp_path, 2)
    warnings: list[str] = []
    result = vm.build_mp4(tmp_path, plans, panels, None, warnings)

    assert result is not None and result.is_file()
    assert any("Ken Burns motion produced a wrong-duration clip" in w for w in warnings)
    assert not any("degraded to fade" in w for w in warnings)  # tier 1 is the normal outcome


def test_kenburns_unavailable_degrades_through_every_tier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(vm.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(vm, "_has_burn_in", lambda: False)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("ffmpeg exploded")

    monkeypatch.setattr(vm.subprocess, "run", _boom)
    plans = [_Plan(3), _Plan(4)]
    panels = _panels(tmp_path, 2)
    warnings: list[str] = []
    result = vm.build_mp4(tmp_path, plans, panels, None, warnings)

    assert result is None
    assert any("ffmpeg video assembly failed" in w for w in warnings)


def test_command_includes_zoompan_filter_and_locked_input_framerate(tmp_path: Path) -> None:
    plan = vm._VideoPlan(
        tmp_path,
        ["-r", "24", "-loop", "1", "-t", "3", "-i", "panel_00.png"],
        [3],
        None,
        1,
        tmp_path / "video_package.mp4",
    )
    argv = plan.command("zoompan", False, "plain", kenburns=True)
    assert "-r" in argv and "24" in argv
    graph = argv[argv.index("-filter_complex") + 1]
    assert "zoompan=" in graph
    assert "concat=n=1" in graph
