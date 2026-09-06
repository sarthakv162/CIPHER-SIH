"""WhisperRuntime and its worker: no heavy import at module load, correct argv, HTTP protocol."""

from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

import pytest

from rupantar.models import runtime_whisper
from rupantar.models.registry import ModelEntry
from rupantar.models.runtime_whisper import WhisperRuntime, _Handler, _main


def test_import_does_not_pull_faster_whisper() -> None:
    assert "faster_whisper" not in sys.modules
    assert "ctranslate2" not in sys.modules


def test_command_carries_model_and_decode_options() -> None:
    entry = ModelEntry(
        key="asr",
        class_="light",
        runtime="whisper",
        path=__import__("pathlib").Path("models/asr/small"),
        args={"compute_type": "int8", "beam_size": 3},
    )
    runtime = WhisperRuntime(entry=entry, port=8123)
    cmd = runtime._command()
    assert cmd[1:3] == ["-m", "rupantar.models.runtime_whisper"]
    assert cmd[cmd.index("--model") + 1] == "models/asr/small"
    assert cmd[cmd.index("--compute-type") + 1] == "int8"
    assert cmd[cmd.index("--beam-size") + 1] == "3"
    assert runtime.endpoint == "http://127.0.0.1:8123"


class _FakeSegment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start, self.end, self.text = start, end, text


class _FakeModel:
    def transcribe(self, audio_path: str, *, beam_size: int) -> tuple[list[_FakeSegment], object]:
        return [_FakeSegment(0.0, 1.2, " hello"), _FakeSegment(1.2, 2.0, " world")], object()


@pytest.fixture()
def worker() -> object:
    runtime_whisper._STATE["model"] = _FakeModel()
    runtime_whisper._STATE["beam_size"] = 1
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        runtime_whisper._STATE.clear()


def test_health_and_transcribe_protocol(worker: str) -> None:
    with urllib.request.urlopen(worker + "/health") as response:
        assert response.status == 200

    request = urllib.request.Request(
        worker + "/transcribe",
        data=json.dumps({"audio_path": "/tmp/x.wav"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        payload = json.loads(response.read())
    assert payload["text"] == "hello world"
    assert [s["text"] for s in payload["segments"]] == [" hello", " world"]
    assert payload["segments"][0]["end"] == 1.2


def test_transcribe_requires_audio_path(worker: str) -> None:
    request = urllib.request.Request(
        worker + "/transcribe", data=b"{}", headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(request)
    assert excinfo.value.code == 400


def test_main_parses_args_and_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        runtime_whisper,
        "_serve",
        lambda port, model, compute, beam: seen.update(
            port=port, model=model, compute=compute, beam=beam
        ),
    )
    _main(["--port", "9001", "--model", "/asr", "--compute-type", "int8", "--beam-size", "2"])
    assert seen == {"port": 9001, "model": "/asr", "compute": "int8", "beam": 2}
