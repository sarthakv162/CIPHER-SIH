"""INV-8: Unload is process termination, never Python garbage collection.

Skeleton only. The real assertions land in phase 1; see PLAN.md section 1 and 6.
"""

from __future__ import annotations

import pytest


def test_unload_kills_process() -> None:
    """INV-8 is enforced from phase 1 onward."""
    pytest.skip("implemented in phase 1")
