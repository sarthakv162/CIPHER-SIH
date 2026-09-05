"""INV-3: Every converter and renderer imports its heavy dependency inside the function.

Skeleton only. The real assertions land in phase 4; see PLAN.md section 1 and 6.
"""

from __future__ import annotations

import pytest


def test_lazy_imports() -> None:
    """INV-3 is enforced from phase 4 onward."""
    pytest.skip("implemented in phase 4")
