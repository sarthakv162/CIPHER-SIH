"""Config loading: locate configs/, read the YAML files, auto-select the hardware profile."""

from __future__ import annotations

import logging
import platform
import shutil
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

from rupantar.core.errors import ConfigError, ProfileError

_DEFAULT_DB_PATH = Path("data/rupantar.db")
_LOG = logging.getLogger("rupantar.config")


def detect_profile() -> tuple[str, str]:
    """Pick a hardware profile from the running machine; return (profile_name, reason)."""
    system, machine = platform.system(), platform.machine()
    if system == "Darwin" and machine in ("arm64", "aarch64"):
        return "apple-metal", f"{system}/{machine} Apple Silicon (llama.cpp Metal)"
    if _has_nvidia():
        return "nvidia-cuda", f"{system}/{machine}, nvidia-smi on PATH"
    return (
        "cpu-only",
        f"{system}/{machine}, no Apple Silicon or nvidia-smi detected — CPU-only fallback",
    )


def _has_nvidia() -> bool:
    """True when `nvidia-smi` is on PATH. Whether the GPU actually works is Phase 8 selfcheck."""
    return shutil.which("nvidia-smi") is not None


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
    profile_source: str
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

    if env.profile:
        active, source = env.profile, "RUPANTAR_PROFILE"
    else:
        active, source = detect_profile()
    if active not in profiles:
        raise ProfileError(
            f"profile {active!r} is not one of {sorted(profiles)}",
            path=str(resolved_dir / "models.yaml"),
            key="active_profile",
        )
    _log_profile(active, source)

    db_path = env.db if env.db is not None else _DEFAULT_DB_PATH

    return AppConfig(
        configs_dir=resolved_dir,
        active_profile=active,
        profile_source=source,
        models=models,
        policy=policy,
        db_path=db_path,
    )


def _log_profile(active: str, source: str) -> None:
    """Announce the resolved profile at INFO; shout when we fell back to cpu-only blind."""
    _LOG.info("hardware profile: %s  (%s)", active, source)
    if active == "cpu-only" and source != "RUPANTAR_PROFILE":
        _LOG.warning(
            "No GPU backend detected — running the cpu-only profile. Generation will be slow "
            "(~2x). If this machine has a GPU, check the llama.cpp build (see README) and set "
            "RUPANTAR_PROFILE to override."
        )
