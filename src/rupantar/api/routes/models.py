"""Model routes deferred from Phase 1: list the registry, show residency, force an unload."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from rupantar.api.app import get_manager, get_registry
from rupantar.core.errors import UnknownModelError
from rupantar.models.manager import ModelManager
from rupantar.models.registry import Registry

router = APIRouter(tags=["models"])


@router.get("/models")
async def list_models(
    registry: Annotated[Registry, Depends(get_registry)],
) -> list[dict[str, object]]:
    """Every model key in the active profile with its class and runtime."""
    rows: list[dict[str, object]] = []
    for key in registry.key_list():
        entry = registry.entry(key)
        rows.append({"key": key, "class": entry.class_, "runtime": entry.runtime})
    return rows


@router.get("/models/status")
async def models_status(
    manager: Annotated[ModelManager, Depends(get_manager)],
) -> list[dict[str, object]]:
    """The manager's residency snapshot for every registered model."""
    return manager.status()


@router.post("/models/{key}/unload")
async def unload_model(
    key: str,
    manager: Annotated[ModelManager, Depends(get_manager)],
    registry: Annotated[Registry, Depends(get_registry)],
) -> dict[str, object]:
    """Evict an idle model now and return its post-eviction status row; 404 for unknown keys."""
    try:
        registry.entry(key)
    except UnknownModelError as exc:
        raise HTTPException(
            status_code=404, detail=f"model {key!r} is not in the active profile"
        ) from exc
    await manager.evict(key)
    for row in manager.status():
        if row["key"] == key:
            return row
    raise HTTPException(status_code=404, detail=f"model {key!r} not found")
