"""Unit coverage for scripts/illustrate_panels.py — a standalone script, not a package module.

Loaded by file path (it lives under scripts/, not src/rupantar/) so these tests never require
torch/diffusers to be installed: the heavy pipeline loader is monkeypatched, never imported.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO / "scripts" / "illustrate_panels.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("illustrate_panels", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


illustrate_panels = _load_module()


def _storyboard(with_extra: bool) -> dict[str, object]:
    scenes = [
        {"visual_recommendation": "a locked server rack", "scene_description": "opening shot"},
        {"visual_recommendation": "a graph trending upward", "scene_description": "the finding"},
        {"visual_recommendation": "a handshake", "scene_description": "closing"},
    ]
    panels = [{"index": 1, "is_extra": False}]
    if with_extra:
        panels.append({"index": 2, "is_extra": True})
    panels += [
        {"index": 3 if with_extra else 2, "is_extra": False},
        {"index": 4 if with_extra else 3, "is_extra": False},
    ]
    return {"scenes": scenes, "panels": panels}


def test_pairing_lands_on_the_right_filenames_without_an_extra_panel() -> None:
    board = _storyboard(with_extra=False)
    pairs = illustrate_panels.pair_scenes_with_panels(board)
    assert [index for _scene, index in pairs] == [1, 2, 3]


def test_pairing_skips_a_spliced_in_extra_panel_index() -> None:
    board = _storyboard(with_extra=True)
    pairs = illustrate_panels.pair_scenes_with_panels(board)
    assert [index for _scene, index in pairs] == [1, 3, 4]
    assert [scene["visual_recommendation"] for scene, _index in pairs] == [
        "a locked server rack",
        "a graph trending upward",
        "a handshake",
    ]


def test_pairing_raises_on_a_genuine_count_mismatch() -> None:
    board = {"scenes": [{}, {}], "panels": [{"index": 1, "is_extra": False}]}
    with pytest.raises(ValueError, match="mismatch"):
        illustrate_panels.pair_scenes_with_panels(board)


def test_build_prompt_combines_visual_and_description() -> None:
    scene = {"visual_recommendation": "a chart", "scene_description": "quarterly results"}
    assert illustrate_panels.build_prompt(scene) == "a chart. quarterly results"


def test_build_prompt_falls_back_when_one_field_is_missing() -> None:
    assert illustrate_panels.build_prompt({"visual_recommendation": "a chart"}) == "a chart"
    assert illustrate_panels.build_prompt({}) == "a plain informational illustration, no text"


def test_model_dir_ready_false_without_model_index(tmp_path: Path) -> None:
    assert illustrate_panels.model_dir_ready(tmp_path) is False
    (tmp_path / "model_index.json").write_text("{}", encoding="utf-8")
    assert illustrate_panels.model_dir_ready(tmp_path) is True


def test_illustrate_raises_and_writes_nothing_when_model_absent(tmp_path: Path) -> None:
    board_path = tmp_path / "storyboard.json"
    board_path.write_text(json.dumps(_storyboard(with_extra=False)), encoding="utf-8")
    out_dir = tmp_path / "out"
    absent_model = tmp_path / "no-such-model"
    with pytest.raises(RuntimeError, match="no usable diffusion model"):
        illustrate_panels.illustrate(board_path, out_dir, steps=1, model_dir=absent_model)
    assert not out_dir.exists()


def test_main_cli_exits_nonzero_with_a_clear_message_when_model_dir_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)  # default model_dir "models/imagegen" is relative to cwd
    board_path = tmp_path / "storyboard.json"
    board_path.write_text(json.dumps(_storyboard(with_extra=False)), encoding="utf-8")
    out_dir = tmp_path / "out"
    code = illustrate_panels.main([str(board_path), "--out", str(out_dir)])
    assert code == 1
    err = capsys.readouterr().err
    assert "no usable diffusion model" in err
    assert not out_dir.exists()


def test_main_cli_exits_nonzero_when_storyboard_file_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = illustrate_panels.main([str(tmp_path / "nope.json"), "--out", str(tmp_path / "o")])
    assert code == 1
    assert "not found" in capsys.readouterr().err
    assert not (tmp_path / "o").exists()


class _FakeImage:
    """Minimal PIL-compatible stand-in wired through a real Pillow round trip."""

    def __init__(self) -> None:
        from PIL import Image

        self._image = Image.new("RGB", (512, 300), "red")

    @property
    def width(self) -> int:
        return self._image.width

    @property
    def height(self) -> int:
        return self._image.height

    def resize(self, size: tuple[int, int], resample: object) -> object:
        return self._image.resize(size, resample)


class _FakeResult:
    def __init__(self) -> None:
        self.images = [_FakeImage()]


class _FakePipe:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, float]] = []

    def __call__(self, prompt: str, num_inference_steps: int, guidance_scale: float) -> _FakeResult:
        self.calls.append((prompt, num_inference_steps, guidance_scale))
        return _FakeResult()


def test_illustrate_writes_one_png_per_scene_with_a_mocked_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "models" / "imagegen"
    model_dir.mkdir(parents=True)
    (model_dir / "model_index.json").write_text("{}", encoding="utf-8")
    board_path = tmp_path / "storyboard.json"
    board_path.write_text(json.dumps(_storyboard(with_extra=True)), encoding="utf-8")
    out_dir = tmp_path / "out"

    fake_pipe = _FakePipe()
    monkeypatch.setattr(illustrate_panels, "_load_pipeline", lambda _model_dir: fake_pipe)

    written = illustrate_panels.illustrate(board_path, out_dir, steps=1, model_dir=model_dir)

    assert sorted(p.name for p in written) == ["panel_01.png", "panel_03.png", "panel_04.png"]
    assert all(p.is_file() for p in written)
    assert len(fake_pipe.calls) == 3
    assert all(steps == 1 and guidance == 0.0 for _prompt, steps, guidance in fake_pipe.calls)

    from PIL import Image

    with Image.open(written[0]) as saved:
        assert saved.size == illustrate_panels.CANVAS


def test_never_imported_by_application_code() -> None:
    """scripts/illustrate_panels.py must not be `import`ed anywhere under src/rupantar/."""
    import ast

    src = _REPO / "src" / "rupantar"
    offenders = []
    for path in src.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                "illustrate_panels" in alias.name for alias in node.names
            ):
                offenders.append(path)
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and "illustrate_panels" in node.module
            ):
                offenders.append(path)
    assert offenders == []


def test_never_referenced_by_models_yaml_or_selfcheck() -> None:
    """scripts/illustrate_panels.py must not be wired into models.yaml or selfcheck."""
    models_yaml = (_REPO / "configs" / "models.yaml").read_text(encoding="utf-8")
    selfcheck = (_REPO / "src" / "rupantar" / "audit" / "selfcheck.py").read_text(encoding="utf-8")
    checks = (_REPO / "src" / "rupantar" / "audit" / "_selfcheck_checks.py").read_text(
        encoding="utf-8"
    )
    assert "illustrate_panels" not in models_yaml
    assert "illustrate_panels" not in selfcheck
    assert "illustrate_panels" not in checks
    assert "imagegen" not in models_yaml
