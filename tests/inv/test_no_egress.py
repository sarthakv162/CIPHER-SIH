"""INV-4: No outbound network connection to a non-loopback address at runtime.

Skeleton only. The real assertions land in phase 8; see PLAN.md section 1 and 6.
"""

from __future__ import annotations

import pytest


def test_no_egress() -> None:
    """INV-4 is enforced from phase 8 onward."""
    pytest.skip("implemented in phase 8")
