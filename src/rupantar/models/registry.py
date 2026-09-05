"""Parse models.yaml for the active profile; verify real model files (stub entries skip)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rupantar.core.config import AppConfig
from rupantar.core.errors import ModelFileMissingError, UnknownModelError

_STUB_RUNTIME = "stub"
_RESERVED_KEYS = {"class", "runtime", "path", "args"}


@dataclass(frozen=True)
class ModelEntry:
    """One resolved model registry row for the active profile."""

    key: str
    class_: str
    runtime: str
    path: Path | None = None
    args: list[Any] | dict[str, Any] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    size_bytes: int | None = None
    sha256: str | None = None

    @property
    def is_stub(self) -> bool:
        """True when this entry uses the file-less stub runtime."""
        return self.runtime == _STUB_RUNTIME


def _sha256(path: Path) -> str:
    """Stream a file through SHA-256 and return the hex digest."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sibling(extra: dict[str, Any], name: str) -> Path | None:
    """Path for an optional sibling file key (mmproj/config) when present."""
    value = extra.get(name)
    return Path(value) if value else None


class Registry:
    """The resolved model registry for one active hardware profile."""

    def __init__(self, entries: dict[str, ModelEntry], runtimes: dict[str, Any]) -> None:
        """Bind resolved entries and the runtimes block from models.yaml."""
        self._entries = entries
        self._runtimes = runtimes

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        verify: bool = True,
        hasher: Callable[[Path], str] = _sha256,
    ) -> Registry:
        """Build the registry for the active profile, verifying non-stub files when `verify`."""
        raw = config.profile_models
        runtimes = config.models.get("runtimes", {})
        entries = {
            key: cls._resolve(key, spec, verify=verify, hasher=hasher) for key, spec in raw.items()
        }
        return cls(entries, runtimes if isinstance(runtimes, dict) else {})

    @classmethod
    def _resolve(
        cls,
        key: str,
        spec: dict[str, Any],
        *,
        verify: bool,
        hasher: Callable[[Path], str],
    ) -> ModelEntry:
        """Turn one YAML row into a ModelEntry, checking files for non-stub runtimes."""
        runtime = str(spec.get("runtime", ""))
        raw_path = spec.get("path")
        path = Path(raw_path) if raw_path else None
        extra = {k: v for k, v in spec.items() if k not in _RESERVED_KEYS}
        size = sha = None
        if runtime != _STUB_RUNTIME and verify:
            size, sha = cls._verify_files(key, path, extra, hasher)
        return ModelEntry(
            key=key,
            class_=str(spec.get("class", "heavy")),
            runtime=runtime,
            path=path,
            args=spec.get("args", []),
            extra=extra,
            size_bytes=size,
            sha256=sha,
        )

    @staticmethod
    def _verify_files(
        key: str,
        path: Path | None,
        extra: dict[str, Any],
        hasher: Callable[[Path], str],
    ) -> tuple[int, str]:
        """Assert the model file and any mmproj/config siblings exist; return size + sha."""
        if path is None:
            raise ModelFileMissingError(
                f"model {key!r} in models.yaml has no 'path'; add one or run "
                "scripts/fetch_models.sh while online",
                key=key,
            )
        candidates = [path, *(_sibling(extra, name) for name in ("mmproj", "config"))]
        for candidate in candidates:
            if candidate is not None and not candidate.is_file():
                raise ModelFileMissingError(
                    f"model file for {key!r} not found at {candidate}; run "
                    "scripts/fetch_models.sh while online to download it",
                    key=key,
                    path=str(candidate),
                )
        return path.stat().st_size, hasher(path)

    def key_list(self) -> list[str]:
        """Every model key defined in the active profile."""
        return list(self._entries)

    def entry(self, key: str) -> ModelEntry:
        """Return the entry for `key` or raise UnknownModelError."""
        try:
            return self._entries[key]
        except KeyError:
            raise UnknownModelError(
                f"model {key!r} is not in the active profile; known keys: {sorted(self._entries)}"
            ) from None

    def runtime_spec(self, name: str) -> dict[str, Any]:
        """Return the runtimes.<name> block from models.yaml, or an empty mapping."""
        spec = self._runtimes.get(name, {})
        return spec if isinstance(spec, dict) else {}
