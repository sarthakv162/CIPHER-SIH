"""Registry parses models.yaml, skips file checks for stub entries, errors on missing files."""

from __future__ import annotations

from pathlib import Path

import pytest

from rupantar.core.config import AppConfig, Env, load_config
from rupantar.core.errors import ModelFileMissingError, UnknownModelError
from rupantar.models.registry import Registry

_CONFIGS = Path(__file__).resolve().parents[2] / "configs"


def _config(profile: str) -> AppConfig:
    return load_config(_CONFIGS, env=Env(profile=profile, db=None))


def test_stub_profile_needs_no_model_files() -> None:
    registry = Registry.from_config(_config("test-stub"), verify=True)
    assert sorted(registry.key_list()) == ["asr", "brain", "tts", "vlm"]
    brain = registry.entry("brain")
    assert brain.is_stub
    assert brain.class_ == "heavy"
    assert brain.path is None
    assert brain.sha256 is None


def test_unknown_key_raises() -> None:
    registry = Registry.from_config(_config("test-stub"))
    with pytest.raises(UnknownModelError):
        registry.entry("nope")


def test_missing_real_file_names_fetch_script(tmp_path: Path) -> None:
    brain = {"class": "heavy", "runtime": "llama", "path": "models/brain/absent.gguf"}
    models = {
        "runtimes": {"llama": {"binary": "llama-server"}},
        "profiles": {"p": {"brain": brain}},
    }
    config = AppConfig(
        configs_dir=tmp_path,
        active_profile="p",
        profile_source="test",
        models=models,
        policy={},
        db_path=tmp_path / "x.db",
    )
    with pytest.raises(ModelFileMissingError) as excinfo:
        Registry.from_config(config, verify=True)
    assert "scripts/fetch_models.sh" in str(excinfo.value)


def test_real_profile_parses_without_verification() -> None:
    registry = Registry.from_config(_config("apple-metal"), verify=False)
    brain = registry.entry("brain")
    assert brain.runtime == "llama"
    assert brain.path == Path("models/brain/Qwen3-4B-Instruct-2507-Q4_K_M.gguf")
    assert "--ctx-size" in brain.args
    assert registry.entry("vlm").extra.get("mmproj")
    assert registry.runtime_spec("llama")["binary"] == "llama-server"


def test_verify_records_size_and_sha_for_present_files(tmp_path: Path) -> None:
    gguf = tmp_path / "brain.gguf"
    gguf.write_bytes(b"hello gguf")
    models = {
        "runtimes": {"llama": {"binary": "llama-server"}},
        "profiles": {"p": {"brain": {"class": "heavy", "runtime": "llama", "path": str(gguf)}}},
    }
    config = AppConfig(
        configs_dir=tmp_path,
        active_profile="p",
        profile_source="test",
        models=models,
        policy={},
        db_path=tmp_path / "x.db",
    )
    brain = Registry.from_config(config, verify=True).entry("brain")
    assert brain.size_bytes == len(b"hello gguf")
    assert brain.sha256 is not None
    assert len(brain.sha256) == 64
