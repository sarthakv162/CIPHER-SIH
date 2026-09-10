"""GET /selfcheck: the offline health report, run off the event loop and without a model load.

`run_selfcheck` is synchronous and shells out to external tools, so it runs in a worker
thread. Its own `asyncio.run` for the live checks is safe there: a worker thread has no running
loop, and `asyncio.Runner` only installs a SIGINT handler on the main thread.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from rupantar.api.app import get_config, get_manager
from rupantar.audit.selfcheck import SelfcheckReport, run_selfcheck
from rupantar.core.config import AppConfig
from rupantar.models.manager import ModelManager

router = APIRouter(tags=["selfcheck"])

_OCCUPIED = ("READY", "LOADING", "EVICTING")


@router.get("/selfcheck")
async def get_selfcheck(
    config: Annotated[AppConfig, Depends(get_config)],
    manager: Annotated[ModelManager, Depends(get_manager)],
    fast: Annotated[bool, Query()] = True,
    load_model: Annotated[bool, Query()] = False,
) -> SelfcheckReport:
    """Run the selfcheck in a worker thread; loads no model unless `load_model=true` is asked.

    The load/unload probe builds its own `ModelManager`, so running it while this
    process already has a model resident could put two heavy models in memory at
    once. That is the one thing the whole design forbids (INV-2), so the probe is
    refused rather than risked whenever this process is holding a model.
    """
    if load_model:
        resident = [row["key"] for row in manager.status() if row["state"] in _OCCUPIED]
        if resident:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"refusing the model load/unload probe while {', '.join(resident)} "
                    "is resident in this process: the probe uses its own model manager, "
                    "and two heavy models must never be resident at once. Retry when the "
                    "transform has finished, or run `python -m rupantar.cli selfcheck` "
                    "in its own process."
                ),
            )
    return await asyncio.to_thread(run_selfcheck, config=config, fast=fast, load_model=load_model)
