"""Config loading: profile resolution, env overrides, and error messages."""

from __future__ import annotations

from pathlib import Path

import pytest

from rupantar.core.config import Env, find_configs_dir, load_config
from rupantar.core.errors import ConfigError, ProfileError

REPO_CONFIGS = Path(__file__).resolve().parents[2] / "configs"


def test_find_configs_dir_locates_repo_configs() -> None:
    assert find_configs_dir().resolve() == REPO_CONFIGS


def test_load_config_default_profile_and_db() -> None:
    config = load_config(REPO_CONFIGS, env=Env(profile=None, db=None))
    assert config.active_profile == "laptop-16gb"
    assert config.db_path == Path("data/rupantar.db")
    assert "brain" in config.profile_models


def test_env_profile_overrides_active_profile() -> None:
    config = load_config(REPO_CONFIGS, env=Env(profile="titan-24gb", db=Path("/tmp/x.db")))
    assert config.active_profile == "titan-24gb"
    assert config.db_path == Path("/tmp/x.db")


def test_unknown_profile_raises_profile_error() -> None:
    with pytest.raises(ProfileError):
        load_config(REPO_CONFIGS, env=Env(profile="nonexistent", db=None))


def test_missing_configs_dir_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path, env=Env(profile=None, db=None))
