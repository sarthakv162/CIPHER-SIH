"""GET /transforms/{id}/events: the live Server-Sent Events stream for the operator console."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from rupantar.api.app import get_bus, get_manager, get_store
from rupantar.api.events import EventBus, StreamEvent, model_payload
from rupantar.core.store import Store
from rupantar.models.manager import ModelManager
from rupantar.orchestrator.progress import transform_payload, verification_payload

router = APIRouter(tags=["events"])

HEARTBEAT_SECONDS = 15.0
# How much load/evict history a late subscriber receives in its snapshot.
_EVENT_TAIL = 40
_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.get("/transforms/{transform_id}/events")
async def transform_events(
    transform_id: str,
    store: Annotated[Store, Depends(get_store)],
    manager: Annotated[ModelManager, Depends(get_manager)],
    bus: Annotated[EventBus, Depends(get_bus)],
) -> StreamingResponse:
    """Stream job, model, token and verification frames until the transform is final."""
    if not await store.list_jobs_for_transform(transform_id):
        raise HTTPException(status_code=404, detail=f"transform {transform_id!r} not found")
    frames = _frames(bus, store, manager, transform_id)
    return StreamingResponse(frames, media_type="text/event-stream", headers=_SSE_HEADERS)


async def _frames(
    bus: EventBus,
    store: Store,
    manager: ModelManager,
    transform_id: str,
    *,
    heartbeat: float = HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """Yield SSE frames: a snapshot, then live events, then one terminal frame."""
    with bus.subscribe(transform_id) as subscriber:
        yield StreamEvent("snapshot", await _snapshot(store, manager, transform_id)).sse()
        if not bus.is_running(transform_id):
            async for frame in _replay_final(store, transform_id):
                yield frame
            return
        while True:
            try:
                event = await asyncio.wait_for(subscriber.queue.get(), heartbeat)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield event.sse()
            if event.name == "transform" and event.data.get("final"):
                return


async def _snapshot(store: Store, manager: ModelManager, transform_id: str) -> dict[str, Any]:
    """Current job rows, model residency, and verification, so a late client is never behind."""
    jobs = await store.list_jobs_for_transform(transform_id)
    report = await store.get_verification_report(transform_id)
    return {
        **transform_payload(transform_id, jobs, final=False),
        "job_rows": [job.model_dump(mode="json") for job in jobs],
        "models": manager.status(),
        # Recent load/evict history too: an operator who opens the run page after a
        # swap has already happened must still see the sequence, not an empty timeline.
        "model_events": [model_payload(event) for event in manager.events[-_EVENT_TAIL:]],
        "verification": verification_payload(transform_id, report) if report else None,
    }


async def _replay_final(store: Store, transform_id: str) -> AsyncIterator[str]:
    """Frames for a transform that already ended: its verification, then a terminal event."""
    report = await store.get_verification_report(transform_id)
    if report is not None:
        yield StreamEvent(
            "verification", verification_payload(transform_id, report), transform_id
        ).sse()
    jobs = await store.list_jobs_for_transform(transform_id)
    yield StreamEvent("transform", transform_payload(transform_id, jobs, final=True)).sse()
