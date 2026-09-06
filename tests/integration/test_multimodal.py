"""Real multimodal dossier: vlm captions keyframes, asr transcribes, peak RSS stays under 10 GB."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rupantar.core.config import Env, load_config
from rupantar.ingest.dossier import assemble_dossier
from rupantar.models.manager import ModelManager
from rupantar.models.registry import Registry

pytestmark = pytest.mark.slow

_REPO = Path(__file__).resolve().parents[2]
_VLM = _REPO / "models" / "vlm"
_ASR = _REPO / "models" / "asr" / "faster-whisper-small.en-int8"
_CLIP = _REPO / "tests" / "fixtures" / "media" / "sample_clip.mp4"
_RSS_LIMIT = 10 * 1024**3


def _missing() -> bool:
    """True when llama-server, a vlm GGUF, or the asr model directory is absent."""
    return (
        shutil.which("llama-server") is None or not list(_VLM.glob("*.gguf")) or not _ASR.is_dir()
    )


class _RssPoller:
    """Background sampler of this process tree's summed RSS."""

    def __init__(self) -> None:
        self.peak = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def __enter__(self) -> _RssPoller:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, _tree_rss_bytes(os.getpid()))
            self._stop.wait(1.0)


def _tree_rss_bytes(root_pid: int) -> int:
    """Summed RSS of `root_pid` and every descendant, via ps/pgrep."""
    pids, frontier = {root_pid}, [root_pid]
    while frontier:
        pid = frontier.pop()
        out = subprocess.run(
            ["pgrep", "-P", str(pid)], capture_output=True, text=True, check=False
        ).stdout.split()
        for child in out:
            if child.isdigit() and int(child) not in pids:
                pids.add(int(child))
                frontier.append(int(child))
    total = 0
    for pid in pids:
        line = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, check=False
        ).stdout.strip()
        if line.isdigit():
            total += int(line) * 1024
    return total


@pytest.mark.skipif(_missing(), reason="needs llama-server, a vlm GGUF, and the asr model dir")
async def test_real_video_dossier_and_peak_rss(tmp_path: Path) -> None:
    from rupantar.core.schemas import SourceInput, SourceKind

    config = load_config(_REPO / "configs", env=Env(profile="apple-metal", db=tmp_path / "r.db"))
    manager = ModelManager(Registry.from_config(config, verify=False), policy=config.policy)
    sources = [SourceInput(kind=SourceKind.file, path=str(_CLIP))]

    with _RssPoller() as poller:
        async with manager:
            dossier, warnings = await assemble_dossier(
                sources,
                manager=manager,
                out_dir=tmp_path / "ingest",
                new_id=lambda: "real-dossier",
                clock=lambda: datetime.now(UTC),
            )

    assert len(dossier.image_insights) >= 2, warnings
    assert dossier.transcripts and dossier.transcripts[0].text.strip()

    order = [(e.kind, e.model_key) for e in manager.events if e.kind.startswith(("LOAD", "EVICT"))]
    assert order == [
        ("LOAD_START", "vlm"),
        ("LOAD_READY", "vlm"),
        ("EVICT_START", "vlm"),
        ("EVICT_DONE", "vlm"),
        ("LOAD_START", "asr"),
        ("LOAD_READY", "asr"),
        ("EVICT_START", "asr"),
        ("EVICT_DONE", "asr"),
    ]
    assert poller.peak < _RSS_LIMIT, f"peak RSS {poller.peak / 1024**3:.1f} GB exceeded 10 GB"
