"""Serve the built operator console from `dist/`, with an SPA fallback and no build required.

Everything here is a no-op until `vite build` has produced a `dist/` directory, so the API,
`make check`, and `TestClient` all work with no frontend on disk.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

_log = logging.getLogger("rupantar.api")

DIST_ENV = "RUPANTAR_FRONTEND_DIST"


def default_dist_dir(configs_dir: Path) -> Path:
    """Where the built console is expected: $RUPANTAR_FRONTEND_DIST, else <repo>/frontend/dist."""
    override = os.environ.get(DIST_ENV)
    return Path(override) if override else configs_dir.parent / "frontend" / "dist"


def api_roots(app: FastAPI) -> frozenset[str]:
    """First path segment of every registered API route, so the SPA never masks a real 404."""
    roots = {
        route.path.split("/")[1]
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/") and "/" in route.path[1:]
    }
    roots |= {route.path.lstrip("/") for route in app.routes if isinstance(route, APIRoute)}
    return frozenset(root for root in roots if root)


class SpaFiles(StaticFiles):
    """Static files that fall back to `index.html` for unknown non-API paths."""

    def __init__(self, *, directory: Path, reserved: frozenset[str]) -> None:
        """Serve `directory`, refusing to shadow any path starting with a reserved segment."""
        super().__init__(directory=directory, html=True)
        self._reserved = reserved

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Serve the file, else `index.html`, else propagate the 404 for API-looking paths."""
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or path.split("/")[0] in self._reserved:
                raise
            return await super().get_response("index.html", scope)


def mount_frontend(app: FastAPI, dist_dir: Path) -> bool:
    """Mount the built console at `/`; returns False and changes nothing when `dist/` is absent."""
    if not (dist_dir / "index.html").is_file():
        _log.info("frontend not mounted: no built dist at %s", dist_dir)
        return False
    app.mount("/", SpaFiles(directory=dist_dir, reserved=api_roots(app)), name="console")
    _log.info("frontend mounted from %s", dist_dir)
    return True
