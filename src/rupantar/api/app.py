"""Rupantar API: assemble the manager, store, and agents once and serve the routers."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request

from rupantar import __version__
from rupantar.agents.base import ArtefactAgent
from rupantar.agents.loader import load_agents
from rupantar.api.events import EventBus
from rupantar.core.config import AppConfig, load_config
from rupantar.core.store import Store
from rupantar.models.manager import ModelManager
from rupantar.models.registry import Registry


def get_config(request: Request) -> AppConfig:
    """The resolved AppConfig stashed on app.state."""
    return request.app.state.config


def get_store(request: Request) -> Store:
    """The shared Store instance."""
    return request.app.state.store


def get_manager(request: Request) -> ModelManager:
    """The single ModelManager for this process."""
    return request.app.state.manager


def get_agents(request: Request) -> dict[str, ArtefactAgent]:
    """The artefact agents keyed by artefact type."""
    return request.app.state.agents


def get_registry(request: Request) -> Registry:
    """The resolved model registry for the active profile."""
    return request.app.state.registry


def get_bus(request: Request) -> EventBus:
    """The single in-process broadcast bus feeding the SSE stream."""
    bus: EventBus = request.app.state.bus
    return bus


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Build the FastAPI app; construct the manager/store/agents but load no model."""
    from rupantar.audit.egress import enforce_offline_env

    logging.getLogger("rupantar").setLevel(logging.INFO)
    enforce_offline_env()
    config = config or load_config()
    registry = Registry.from_config(config, verify=False)
    bus = EventBus()
    manager = ModelManager(registry, policy=config.policy, event_sink=bus.model_sink)
    store = Store(config.db_path)
    agents = load_agents(config.configs_dir / "agents")

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Open the store on startup; tear the store and every model process down on shutdown."""
        # policy.prewarm_on_startup is deliberately NOT honoured — auto-spawning llama-server
        # on startup breaks TestClient; the first transform triggers the load instead.
        enforce_offline_env()
        await store.connect()
        try:
            yield
        finally:
            await manager.aclose()
            await store.close()

    app = FastAPI(title="Rupantar", version=__version__ or "0", lifespan=lifespan)
    app.state.config = config
    app.state.registry = registry
    app.state.manager = manager
    app.state.store = store
    app.state.agents = agents
    app.state.bus = bus
    app.state.tasks = set()

    from rupantar.api.routes import (
        convert,
        events,
        files,
        health,
        jobs,
        models,
        release,
        templates,
        transforms,
    )
    from rupantar.api.static import default_dist_dir, mount_frontend

    app.include_router(health.router)
    app.include_router(transforms.router)
    app.include_router(events.router)
    app.include_router(release.router)
    app.include_router(files.router)
    app.include_router(jobs.router)
    app.include_router(models.router)
    app.include_router(convert.router)
    app.include_router(templates.router)
    mount_frontend(app, default_dist_dir(config.configs_dir))
    return app
