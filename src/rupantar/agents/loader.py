"""Build ArtefactAgent instances from configs/agents/*.yaml."""

from __future__ import annotations

import importlib
from pathlib import Path
from string import Template
from typing import Any

import yaml

from rupantar.agents.base import ArtefactAgent
from rupantar.core.artefacts import ArtefactBase
from rupantar.core.errors import ConfigError

_REQUIRED = (
    "artefact_type",
    "model_key",
    "system_prompt",
    "user_template",
    "schema",
    "max_tokens",
    "temperature",
)


def load_agent(path: Path) -> ArtefactAgent:
    """Build one ArtefactAgent from a single agent YAML file."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError("agent config is not a mapping", path=str(path))
    missing = [key for key in _REQUIRED if key not in raw]
    if missing:
        raise ConfigError(f"agent config missing keys {missing}", path=str(path))
    return ArtefactAgent(
        artefact_type=str(raw["artefact_type"]),
        model_key=str(raw["model_key"]),
        system_prompt=str(raw["system_prompt"]),
        user_template=Template(str(raw["user_template"])),
        schema=_import_schema(str(raw["schema"]), path),
        max_tokens=int(raw["max_tokens"]),
        temperature=float(raw["temperature"]),
        param_hints=_coerce_hints(raw.get("param_hints", {})),
    )


def load_agents(directory: Path) -> dict[str, ArtefactAgent]:
    """Load every *.yaml agent config in `directory`, keyed by artefact_type."""
    agents: dict[str, ArtefactAgent] = {}
    for path in sorted(directory.glob("*.yaml")):
        agent = load_agent(path)
        agents[agent.artefact_type] = agent
    return agents


def _import_schema(dotted: str, path: Path) -> type[ArtefactBase]:
    """Import the `module:ClassName` schema and confirm it is an ArtefactBase subclass."""
    if ":" not in dotted:
        raise ConfigError(
            f"schema {dotted!r} must be 'module:ClassName'", path=str(path), key="schema"
        )
    module_name, class_name = dotted.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        raise ConfigError(
            f"cannot import schema {dotted!r}: {exc}", path=str(path), key="schema"
        ) from exc
    if not (isinstance(cls, type) and issubclass(cls, ArtefactBase)):
        raise ConfigError(
            f"schema {dotted!r} is not an ArtefactBase subclass", path=str(path), key="schema"
        )
    return cls


def _coerce_hints(value: Any) -> dict[str, dict[str, str]]:
    """Normalise the param_hints block to `param -> {value -> phrase}` of strings."""
    if not isinstance(value, dict):
        return {}
    return {
        str(param): {str(key): str(phrase) for key, phrase in table.items()}
        for param, table in value.items()
        if isinstance(table, dict)
    }
