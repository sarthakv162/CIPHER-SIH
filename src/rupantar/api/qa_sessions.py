"""In-memory evidence-pack sessions for the console's "Ask about sources" mode.

Deliberately not a Transform: no `Store` row, no `Job`, no manifest. A session's dossier
lives only in this process's memory for the life of the process, and the store is capped
so a long-running demo cannot leak memory across many attach/ask cycles.
"""

from __future__ import annotations

from rupantar.core.schemas import SourceDossier

DEFAULT_CAPACITY = 20


class QaSessionStore:
    """A small drop-oldest cache of assembled dossiers, keyed by a generated session id."""

    def __init__(self, *, capacity: int = DEFAULT_CAPACITY) -> None:
        """Create an empty store with a fixed capacity."""
        self._capacity = capacity
        self._sessions: dict[str, SourceDossier] = {}

    def put(self, session_id: str, dossier: SourceDossier) -> None:
        """Store a dossier under `session_id`, evicting the oldest session over capacity."""
        self._sessions[session_id] = dossier
        while len(self._sessions) > self._capacity:
            self._sessions.pop(next(iter(self._sessions)))

    def get(self, session_id: str) -> SourceDossier | None:
        """Return the dossier for `session_id`, or None if it is unknown or evicted."""
        return self._sessions.get(session_id)
