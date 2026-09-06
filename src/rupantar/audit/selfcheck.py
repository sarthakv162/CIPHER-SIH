"""The offline system health report: eight checks, a table or JSON, non-zero exit on failure."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field

from rupantar.audit.egress import scan_egress
from rupantar.core.config import AppConfig, load_config

_LEVELS = {"ok", "warn", "fail"}
_BADGE = {"ok": "[ OK ]", "warn": "[WARN]", "fail": "[FAIL]"}


class CheckResult(BaseModel):
    """One row of the selfcheck report."""

    number: str
    name: str
    level: str = Field(pattern="^(ok|warn|fail)$")
    detail: str
    data: dict[str, Any] = Field(default_factory=dict)


class SelfcheckReport(BaseModel):
    """The full selfcheck outcome."""

    generated_at: str
    profile: str
    profile_source: str
    checks: list[CheckResult]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ok(self) -> bool:
        """True when no check failed (warnings are tolerated)."""
        return all(check.level != "fail" for check in self.checks)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def result(self) -> str:
        """PASS / FAIL headline for machine consumers of the JSON report."""
        return "PASS" if self.ok else "FAIL"

    @property
    def exit_code(self) -> int:
        """0 when every check passed, 1 otherwise."""
        return 0 if self.ok else 1

    def table(self) -> str:
        """Render the report as a fixed-width text table."""
        width = max((len(c.name) for c in self.checks), default=4)
        lines = [
            f"Rupantar selfcheck — profile {self.profile} ({self.profile_source})",
            f"{'#':<3} {'CHECK':<{width}} STATUS  DETAIL",
            "-" * (width + 60),
        ]
        for check in self.checks:
            lines.append(
                f"{check.number:<3} {check.name:<{width}} {_BADGE[check.level]}  {check.detail}"
            )
        verdict = "PASS" if self.ok else "FAIL"
        lines.append("-" * (width + 60))
        lines.append(f"result: {verdict}")
        return "\n".join(lines)


async def _live_checks(config: AppConfig, *, load_model: bool) -> list[CheckResult]:
    """Run the two checks that need an event loop (4b offload, 5 model manager)."""
    from rupantar.audit._selfcheck_hw import check_hw_offload, check_model_manager

    results = await check_hw_offload(config, load_model=load_model)
    results += await check_model_manager(config, load_model=load_model)
    return results


def run_selfcheck(
    *,
    config: AppConfig | None = None,
    fast: bool = False,
    load_model: bool = True,
) -> SelfcheckReport:
    """Run all eight checks and return the report. `fast` skips model-file hashing."""
    from rupantar.audit._selfcheck_checks import (
        check_converters,
        check_egress_now,
        check_model_files,
        check_ports,
        check_python,
        check_renderers,
        check_tools,
    )

    config = config or load_config()
    baseline_clean = scan_egress().clean

    checks: list[CheckResult] = []
    checks += check_python()
    checks += check_tools()
    checks += check_model_files(config, fast=fast)
    checks += check_ports(config)
    checks += asyncio.run(_live_checks(config, load_model=load_model))
    checks += check_renderers()
    checks += check_converters()
    checks += check_egress_now(baseline_clean)

    return SelfcheckReport(
        generated_at=datetime.now(UTC).isoformat(),
        profile=config.active_profile,
        profile_source=config.profile_source,
        checks=checks,
    )
