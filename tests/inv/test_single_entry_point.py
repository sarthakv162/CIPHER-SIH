"""INV-7: ModelManager.acquire() is the only code path that starts a model process.

Model process spawning must be confined to src/rupantar/models/runtime_*.py. Every other
module under src/rupantar/ is scanned for subprocess / os.spawn / create_subprocess /
multiprocessing. `ingest/video.py` is exempt for the bare `subprocess` name only: it shells
out to ffmpeg/ffprobe for keyframes and audio extraction, which are media tools, not models
(see MEMORY.md Phase 6 deviation). `render/video_render.py` is exempt on the same grounds: it
shells out to ffmpeg/piper to assemble the video package. `audit/_selfcheck_checks.py` is
exempt on the same grounds: selfcheck check 2 probes `ffmpeg --version` / `llama-server
--version` / `piper --version` with subprocess.run to report tool versions. It never serves
inference and starts no model process (the offload probe in check 4b goes through
ModelManager.acquire like everything else). `render/_video_mux.py` and `render/_video_scene.py`
are exempt on the same grounds as `render/video_render.py`: they shell out to ffmpeg for mp4
assembly and b-roll frame extraction. All exempt modules still must not use Popen /
os.spawn / multiprocessing.
"""

from __future__ import annotations

import re
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "rupantar"
_MEDIA_TOOL_MODULES = {
    "ingest/video.py",
    "render/video_render.py",
    "render/_video_mux.py",
    "render/_video_scene.py",
    "audit/_selfcheck_checks.py",
}
_SUBPROCESS_NAME = re.compile(r"\bsubprocess\b")

_FORBIDDEN = [
    _SUBPROCESS_NAME,
    re.compile(r"\bPopen\b"),
    re.compile(r"\bos\.spawn"),
    re.compile(r"\bos\.posix_spawn"),
    re.compile(r"create_subprocess_(exec|shell)"),
    re.compile(r"\bmultiprocessing\b"),
]


def _is_runtime_module(path: Path) -> bool:
    return path.name.startswith("runtime_")


def test_only_runtime_modules_spawn_processes() -> None:
    offenders: list[str] = []
    for path in _SRC.rglob("*.py"):
        if _is_runtime_module(path):
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(_SRC).as_posix()
        for pattern in _FORBIDDEN:
            if pattern is _SUBPROCESS_NAME and rel in _MEDIA_TOOL_MODULES:
                continue
            if pattern.search(text):
                offenders.append(f"{rel} :: /{pattern.pattern}/")
    assert not offenders, f"process spawning found outside runtime_*.py: {offenders}"


def test_manager_exposes_acquire_as_the_entry_point() -> None:
    from rupantar.models.manager import ModelManager

    assert hasattr(ModelManager, "acquire")
    assert hasattr(ModelManager, "obtain")


def test_runtime_modules_do_spawn() -> None:
    runtime_text = "\n".join(
        p.read_text(encoding="utf-8") for p in _SRC.glob("models/runtime_*.py")
    )
    assert "subprocess" in runtime_text
