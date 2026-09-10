"""`POST /sources` takes a browser-supplied filename, so its sanitiser is attack surface."""

from __future__ import annotations

import pytest

from rupantar.api.routes.uploads import ALLOWED_SUFFIXES, sanitise, unique_path


@pytest.mark.parametrize(
    "hostile",
    [
        "../../etc/passwd",
        "..\\..\\windows\\system32\\config",
        "/etc/passwd",
        "..",
        ".",
        "",
        "   ",
        "a\x00b.md",
        "report\r\nX-Injected: 1.md",
        "....//....//x.md",
    ],
)
def test_hostile_names_never_survive_as_a_traversable_segment(hostile: str) -> None:
    """Whatever comes back must be a single, separator-free, printable segment."""
    cleaned = sanitise(hostile)
    assert "/" not in cleaned
    assert "\\" not in cleaned
    assert "\x00" not in cleaned
    assert cleaned not in {".", ".."}
    assert all(ch.isprintable() for ch in cleaned)


def test_a_traversal_prefix_is_stripped_to_its_basename() -> None:
    """`../../x.md` becomes `x.md` — kept, but only inside the upload directory."""
    assert sanitise("../../x.md") == "x.md"
    assert sanitise("..%2F..%2Fx.md".replace("%2F", "/")) == "x.md"


def test_ordinary_names_are_left_alone() -> None:
    assert sanitise("incident report.pdf") == "incident report.pdf"
    assert sanitise("brief.md") == "brief.md"


def test_a_leading_dot_cannot_write_a_dotfile() -> None:
    """`.bashrc` must not land as a dotfile in the upload directory."""
    assert not sanitise(".bashrc").startswith(".")


def test_executable_suffixes_are_not_accepted_source_types() -> None:
    for suffix in (".sh", ".exe", ".py", ".dylib", ".so", ""):
        assert suffix not in ALLOWED_SUFFIXES


def test_a_colliding_name_gets_a_suffix_instead_of_overwriting(tmp_path) -> None:
    """An upload never silently replaces an earlier one."""
    (tmp_path / "brief.md").write_text("first")
    target = unique_path(tmp_path, "brief.md")
    assert target.name == "brief-1.md"
    assert (tmp_path / "brief.md").read_text() == "first"
