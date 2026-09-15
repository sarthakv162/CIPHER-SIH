"""POST /transforms/{id}/ask and POST /qa/sessions[/{id}/ask]: question answering over an
evidence pack, streamed over SSE.

Reuses the resident brain through `ModelManager.acquire("brain")` -- no new model. Answers
from the whole dossier text in the prompt -- no retrieval. Never creates a `Transform`,
`Job`, or manifest -- see `orchestrator/qa.py` for the prompt and `api/qa_sessions.py` for
the in-memory, non-persisted evidence pack a session holds before any transform exists.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rupantar.api.app import get_config, get_manager, get_qa_sessions, get_store
from rupantar.api.events import StreamEvent
from rupantar.api.qa_sessions import QaSessionStore
from rupantar.core.config import AppConfig
from rupantar.core.errors import ModelError
from rupantar.core.schemas import SourceDossier, SourceInput
from rupantar.core.store import Store
from rupantar.ingest.dossier import assemble_dossier
from rupantar.models.client import LlamaClient
from rupantar.models.manager import ModelManager
from rupantar.orchestrator.qa import answer_stream

router = APIRouter(tags=["ask"])

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


class AskRequest(BaseModel):
    """One question against an already-loaded evidence pack."""

    question: Annotated[str, Field(min_length=1, max_length=2000)]


class SessionRequest(BaseModel):
    """Sources to ingest into a session-scoped evidence pack; never persisted as a Transform."""

    sources: Annotated[list[SourceInput], Field(min_length=1)]


class SessionCreated(BaseModel):
    """The id of a freshly assembled, in-memory evidence pack."""

    session_id: str


def _uuid() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(UTC)


@router.post("/transforms/{transform_id}/ask")
async def ask_transform(
    transform_id: str,
    body: AskRequest,
    store: Annotated[Store, Depends(get_store)],
    manager: Annotated[ModelManager, Depends(get_manager)],
) -> StreamingResponse:
    """Stream an answer grounded only in `transform_id`'s already-ingested evidence pack."""
    if not await store.list_jobs_for_transform(transform_id):
        raise HTTPException(status_code=404, detail=f"transform {transform_id!r} not found")
    dossier = await store.get_dossier(transform_id)
    if dossier is None or not dossier.sha256:
        raise HTTPException(
            status_code=409,
            detail=f"transform {transform_id!r} has no ingested evidence yet",
        )
    return StreamingResponse(
        _answer(dossier, body.question, manager),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/qa/sessions", status_code=201)
async def create_session(
    body: SessionRequest,
    config: Annotated[AppConfig, Depends(get_config)],
    manager: Annotated[ModelManager, Depends(get_manager)],
    sessions: Annotated[QaSessionStore, Depends(get_qa_sessions)],
) -> SessionCreated:
    """Ingest `sources` into an in-memory evidence pack: never a Transform, never on disk."""
    session_id = _uuid()
    out_dir = config.db_path.parent / "qa_sessions" / session_id / "_ingest"
    dossier, _warnings = await assemble_dossier(
        body.sources,
        manager=manager,
        out_dir=out_dir,
        new_id=lambda: session_id,
        clock=_utcnow,
    )
    sessions.put(session_id, dossier)
    return SessionCreated(session_id=session_id)


@router.post("/qa/sessions/{session_id}/ask")
async def ask_session(
    session_id: str,
    body: AskRequest,
    manager: Annotated[ModelManager, Depends(get_manager)],
    sessions: Annotated[QaSessionStore, Depends(get_qa_sessions)],
) -> StreamingResponse:
    """Stream an answer grounded only in the session's in-memory evidence pack."""
    dossier = sessions.get(session_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail=f"qa session {session_id!r} not found")
    return StreamingResponse(
        _answer(dossier, body.question, manager),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


async def _answer(
    dossier: SourceDossier, question: str, manager: ModelManager
) -> AsyncIterator[str]:
    """Acquire the brain, stream `delta` SSE frames, then one `done` (or `error`) frame."""
    try:
        async with manager.acquire("brain") as lease:
            client = LlamaClient(lease.endpoint)
            try:
                async for delta in answer_stream(dossier.to_prompt_text(), question, client):
                    yield StreamEvent("delta", {"text": delta}).sse()
            finally:
                await client.aclose()
    except ModelError as exc:
        yield StreamEvent("error", {"detail": str(exc)}).sse()
        return
    yield StreamEvent("done", {}).sse()
