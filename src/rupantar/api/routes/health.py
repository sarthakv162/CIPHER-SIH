"""GET /health: process liveness, active profile, Python version, resident model count."""

from __future__ import annotations

import platform
from typing import Annotated

from fastapi import APIRouter, Depends

from rupantar.api.app import get_config, get_manager
from rupantar.audit.egress import accumulated_violations, scan_egress
from rupantar.core.config import AppConfig
from rupantar.models.manager import ModelManager

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    config: Annotated[AppConfig, Depends(get_config)],
    manager: Annotated[ModelManager, Depends(get_manager)],
) -> dict[str, object]:
    """Report status, active profile, running Python, and how many models are READY."""
    resident = sum(1 for row in manager.status() if row["state"] == "READY")
    return {
        "status": "ok",
        "profile": config.active_profile,
        "profile_source": config.profile_source,
        "platform": f"{platform.system()}/{platform.machine()}",
        "python": platform.python_version(),
        "models_resident": resident,
    }


@router.get("/health/egress")
async def health_egress() -> dict[str, object]:
    """Scan this process tree for non-loopback connections now, plus any seen earlier."""
    report = scan_egress()
    earlier = [v.as_dict() for v in accumulated_violations()]
    return {
        "checked_at": report.checked_at,
        "clean": report.clean and not earlier,
        "violations": [*[v.as_dict() for v in report.violations], *earlier],
        "scanned_pids": report.scanned_pids,
    }
