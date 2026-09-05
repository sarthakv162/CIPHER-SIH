"""Typed exception hierarchy. Every message names the file or key at fault."""

from __future__ import annotations


class RupantarError(Exception):
    """Base class for every error raised by Rupantar."""


class ConfigError(RupantarError):
    """A configuration file is missing, unreadable, or has a bad key."""

    def __init__(self, message: str, *, path: str | None = None, key: str | None = None) -> None:
        """Record the offending path/key alongside the human-readable message."""
        self.path = path
        self.key = key
        location = " ".join(
            part for part in (f"file={path}" if path else "", f"key={key}" if key else "") if part
        )
        super().__init__(f"{message} ({location})" if location else message)


class ProfileError(ConfigError):
    """The requested hardware profile is not defined in models.yaml."""


class SchemaValidationError(RupantarError):
    """A payload failed Pydantic validation against a frozen contract."""


class StoreError(RupantarError):
    """A persistence operation failed or found no matching row."""

    def __init__(
        self, message: str, *, entity: str | None = None, row_id: str | None = None
    ) -> None:
        """Record the entity and id involved in the failed persistence call."""
        self.entity = entity
        self.row_id = row_id
        suffix = " ".join(
            part
            for part in (f"entity={entity}" if entity else "", f"id={row_id}" if row_id else "")
            if part
        )
        super().__init__(f"{message} ({suffix})" if suffix else message)


class NotAvailableYetError(RupantarError):
    """A capability exists as a stub and lands in a later phase."""
