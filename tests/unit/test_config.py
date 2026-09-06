"""Config loading: hardware detection, profile resolution, env override, error messages."""

from __future__ import annotations

from pathlib import Path

import pytest

from rupantar.core import config as config_mod
from rupantar.core.config import Env, detect_profile, find_configs_dir, load_config
from rupantar.core.errors import ConfigError, ProfileError

REPO_CONFIGS = Path(__file__).resolve().parents[2] / "configs"
_AUTO = {"apple-metal", "nvidia-cuda", "cpu-only"}


def test_find_configs_dir_locates_repo_configs() -> None:
    assert find_configs_dir().resolve() == REPO_CONFIGS


def test_detect_profile_returns_a_known_profile_and_reason() -> None:
    profile, reason = detect_profile()
    assert profile in _AUTO
    assert reason


def test_detect_apple_silicon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_mod.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(config_mod.platform, "machine", lambda: "arm64")
    assert detect_profile()[0] == "apple-metal"


def test_detect_nvidia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(config_mod.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(config_mod, "_has_nvidia", lambda: True)
    assert detect_profile()[0] == "nvidia-cuda"


def test_detect_falls_back_to_cpu_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(config_mod.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(config_mod, "_has_nvidia", lambda: False)
    profile, reason = detect_profile()
    assert profile == "cpu-only"
    assert "fallback" in reason.lower()


def test_load_config_auto_selects_a_profile() -> None:
    config = load_config(REPO_CONFIGS, env=Env(profile=None, db=None))
    assert config.active_profile in _AUTO
    assert config.profile_source != "RUPANTAR_PROFILE"
    assert config.db_path == Path("data/rupantar.db")
    assert "brain" in config.profile_models


def test_env_profile_overrides_detection() -> None:
    config = load_config(REPO_CONFIGS, env=Env(profile="titan-24gb", db=Path("/tmp/x.db")))
    assert config.active_profile == "titan-24gb"
    assert config.profile_source == "RUPANTAR_PROFILE"
    assert config.db_path == Path("/tmp/x.db")


def test_cpu_only_fallback_logs_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(config_mod, "detect_profile", lambda: ("cpu-only", "no GPU"))
    with caplog.at_level("WARNING", logger="rupantar.config"):
        load_config(REPO_CONFIGS, env=Env(profile=None, db=None))
    assert any("cpu-only" in r.message for r in caplog.records)


def test_unknown_profile_raises_profile_error() -> None:
    with pytest.raises(ProfileError):
        load_config(REPO_CONFIGS, env=Env(profile="nonexistent", db=None))


def test_missing_configs_dir_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path, env=Env(profile=None, db=None))
