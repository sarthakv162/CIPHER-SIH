"""Async SQLite persistence for dossiers, transforms, and jobs. JSON text columns."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

import aiosqlite

from rupantar.core.errors import StoreError
from rupantar.core.schemas import Job, SourceDossier, TransformRequest
from rupantar.verify.report import VerificationReport

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dossiers (
    id         TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    data_json  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verification_reports (
    transform_id TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL,
    data_json    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transforms (
    id         TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    data_json  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    transform_id  TEXT NOT NULL,
    artefact_type TEXT NOT NULL,
    model_key     TEXT NOT NULL,
    status        TEXT NOT NULL,
    data_json     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_transform ON jobs (transform_id);
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    kind        TEXT NOT NULL,
    model_key   TEXT,
    pid         INTEGER,
    detail_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events (kind);
"""


class Store:
    """A thin async wrapper over one SQLite database file."""

    def __init__(self, db_path: Path | str) -> None:
        """Bind the store to a database path without opening it."""
        self._db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    @property
    def connection(self) -> aiosqlite.Connection:
        """The open connection, or raise if `connect()` has not run."""
        if self._conn is None:
            raise StoreError("store is not connected; call connect() first")
        return self._conn

    async def connect(self) -> None:
        """Open the connection and create tables if they do not exist."""
        if self._conn is not None:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        """Close the connection if it is open."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def __aenter__(self) -> Store:
        """Open the store for use as an async context manager."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the store on context exit."""
        await self.close()

    async def save_dossier(self, dossier: SourceDossier) -> None:
        """Insert or replace one dossier row."""
        await self.connection.execute(
            "INSERT OR REPLACE INTO dossiers (id, created_at, data_json) VALUES (?, ?, ?)",
            (dossier.id, dossier.created_at.isoformat(), dossier.model_dump_json()),
        )
        await self.connection.commit()

    async def get_dossier(self, dossier_id: str) -> SourceDossier | None:
        """Return the dossier with this id, or None."""
        async with self.connection.execute(
            "SELECT data_json FROM dossiers WHERE id = ?", (dossier_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return SourceDossier.model_validate_json(row["data_json"]) if row else None

    async def save_verification_report(self, transform_id: str, report: VerificationReport) -> None:
        """Insert or replace one verification report row, keyed by transform."""
        await self.connection.execute(
            "INSERT OR REPLACE INTO verification_reports "
            "(transform_id, created_at, data_json) VALUES (?, ?, ?)",
            (transform_id, datetime.now(UTC).isoformat(), report.model_dump_json()),
        )
        await self.connection.commit()

    async def get_verification_report(self, transform_id: str) -> VerificationReport | None:
        """Return the verification report for a Transform, or None if none has run yet."""
        async with self.connection.execute(
            "SELECT data_json FROM verification_reports WHERE transform_id = ?", (transform_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return VerificationReport.model_validate_json(row["data_json"]) if row else None

    async def create_transform(self, transform_id: str, request: TransformRequest) -> None:
        """Persist one Transform (the batch request) under the given id."""
        await self.connection.execute(
            "INSERT INTO transforms (id, created_at, data_json) VALUES (?, ?, ?)",
            (transform_id, datetime.now(UTC).isoformat(), request.model_dump_json()),
        )
        await self.connection.commit()

    async def get_transform_request(self, transform_id: str) -> TransformRequest | None:
        """Return the stored request for a Transform, or None."""
        async with self.connection.execute(
            "SELECT data_json FROM transforms WHERE id = ?", (transform_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return TransformRequest.model_validate_json(row["data_json"]) if row else None

    async def create_job(self, job: Job) -> None:
        """Insert one job row."""
        await self.connection.execute(
            "INSERT INTO jobs (id, transform_id, artefact_type, model_key, status, data_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                job.id,
                job.transform_id,
                job.artefact_type.value,
                job.model_key,
                job.status.value,
                job.model_dump_json(),
            ),
        )
        await self.connection.commit()

    async def get_job(self, job_id: str) -> Job | None:
        """Return the job with this id, or None."""
        async with self.connection.execute(
            "SELECT data_json FROM jobs WHERE id = ?", (job_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return Job.model_validate_json(row["data_json"]) if row else None

    async def update_job(self, job: Job) -> None:
        """Replace an existing job row; raise if the id is unknown."""
        cursor = await self.connection.execute(
            "UPDATE jobs SET transform_id = ?, artefact_type = ?, model_key = ?, "
            "status = ?, data_json = ? WHERE id = ?",
            (
                job.transform_id,
                job.artefact_type.value,
                job.model_key,
                job.status.value,
                job.model_dump_json(),
                job.id,
            ),
        )
        await self.connection.commit()
        if cursor.rowcount == 0:
            raise StoreError("cannot update unknown job", entity="jobs", row_id=job.id)

    async def append_event(
        self,
        *,
        kind: str,
        model_key: str | None = None,
        pid: int | None = None,
        ts: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Append one model-manager or runtime event row."""
        await self.connection.execute(
            "INSERT INTO events (ts, kind, model_key, pid, detail_json) VALUES (?, ?, ?, ?, ?)",
            (
                ts or datetime.now(UTC).isoformat(),
                kind,
                model_key,
                pid,
                json.dumps(detail or {}),
            ),
        )
        await self.connection.commit()

    async def list_events(
        self, *, kind: str | None = None, model_key: str | None = None
    ) -> list[dict[str, Any]]:
        """Return event rows filtered by kind and/or model_key, oldest first."""
        clauses: list[str] = []
        params: list[str] = []
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if model_key is not None:
            clauses.append("model_key = ?")
            params.append(model_key)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        async with self.connection.execute(
            f"SELECT id, ts, kind, model_key, pid, detail_json FROM events{where} ORDER BY id",
            params,
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "ts": row["ts"],
                "kind": row["kind"],
                "model_key": row["model_key"],
                "pid": row["pid"],
                "detail": json.loads(row["detail_json"]),
            }
            for row in rows
        ]

    async def list_jobs_for_transform(self, transform_id: str) -> list[Job]:
        """Return every job belonging to a Transform, in insertion order."""
        async with self.connection.execute(
            "SELECT data_json FROM jobs WHERE transform_id = ? ORDER BY rowid", (transform_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [Job.model_validate_json(row["data_json"]) for row in rows]
