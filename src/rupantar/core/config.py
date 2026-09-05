"""Minimal config loading: locate configs/, read the YAML files, resolve the active profile."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

from rupantar.core.errors import ConfigError, ProfileError

_DEFAULT_DB_PATH = Path("data/rupantar.db")


class Env(BaseSettings):
    """Environment overrides. `RUPANTAR_PROFILE` and `RUPANTAR_DB` are the only keys read now."""

    model_config = SettingsConfigDict(env_prefix="RUPANTAR_", extra="ignore")

    profile: str | None = None
    db: Path | None = None


class AppConfig(BaseModel):
    """Resolved configuration for one process run."""

    model_config = ConfigDict(frozen=True)

    configs_dir: Path
    active_profile: str
    models: dict[str, Any]
    policy: dict[str, Any]
    db_path: Path

    @property
    def profile_models(self) -> dict[str, Any]:
        """The model registry entries for the active profile."""
        profiles: dict[str, Any] = self.models.get("profiles", {})
        return profiles[self.active_profile]


def find_configs_dir(start: Path | None = None) -> Path:
    """Return the first directory containing models.yaml, searching upward from `start`/module."""
    seeds: list[Path] = []
    if start is not None:
        seeds.append(Path(start))
    seeds.append(Path.cwd())
    seeds.append(Path(__file__).resolve().parent)

    seen: set[Path] = set()
    for seed in seeds:
        for base in (seed, *seed.parents):
            candidate = base / "configs"
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / "models.yaml").is_file():
                return candidate
    raise ConfigError("could not locate configs/models.yaml from any parent directory")


def _load_yaml(path: Path) -> dict[str, Any]:
    """Parse a YAML mapping file, raising ConfigError with the path on any failure."""
    if not path.is_file():
        raise ConfigError("config file not found", path=str(path))
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML: {exc}", path=str(path)) from exc
    if not isinstance(data, dict):
        raise ConfigError("expected a top-level mapping", path=str(path))
    return data


def load_config(configs_dir: Path | None = None, env: Env | None = None) -> AppConfig:
    """Load models.yaml + policy.yaml and resolve the active profile and SQLite path."""
    resolved_dir = Path(configs_dir) if configs_dir is not None else find_configs_dir()
    env = env or Env()

    models = _load_yaml(resolved_dir / "models.yaml")
    policy = _load_yaml(resolved_dir / "policy.yaml")

    profiles = models.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ConfigError(
            "no profiles defined", path=str(resolved_dir / "models.yaml"), key="profiles"
        )

    active = env.profile or models.get("active_profile")
    if not active:
        raise ConfigError(
            "no active profile: set RUPANTAR_PROFILE or models.yaml:active_profile",
            path=str(resolved_dir / "models.yaml"),
            key="active_profile",
        )
    if active not in profiles:
        raise ProfileError(
            f"profile {active!r} is not one of {sorted(profiles)}",
            path=str(resolved_dir / "models.yaml"),
            key="active_profile",
        )

    db_path = env.db if env.db is not None else _DEFAULT_DB_PATH

    return AppConfig(
        configs_dir=resolved_dir,
        active_profile=active,
        models=models,
        policy=policy,
        db_path=db_path,
    )
