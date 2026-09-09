"""Path-safety unit tests: no operator-supplied name may escape a job's output directory."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from rupantar.api.paths import job_files, resolve_job_file, safe_file_name


@pytest.fixture
def job_dir(tmp_path: Path) -> Path:
    """A job output directory holding one artefact and its sibling manifest."""
    directory = tmp_path / "outputs" / "job-1"
    directory.mkdir(parents=True)
    (directory / "advisory.pdf").write_bytes(b"%PDF-1.4 fake")
    (directory / "advisory.pdf.manifest.json").write_text("{}", encoding="utf-8")
    (directory / "advisory.md").write_text("# advisory", encoding="utf-8")
    return directory


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        "../advisory.pdf",
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "sub/advisory.pdf",
        "/etc/passwd",
        "/",
        "advisory\x00.pdf",
        "advisory\n.pdf",
        "advisory\r\nX-Injected: 1",
        "advisory\x7f.pdf",
    ],
)
def test_safe_file_name_rejects_hostile_names(name: str) -> None:
    assert safe_file_name(name) is False


@pytest.mark.parametrize("name", ["advisory.pdf", "panel_01.png", ".hidden", "a b.md", "x..y.md"])
def test_safe_file_name_accepts_ordinary_names(name: str) -> None:
    assert safe_file_name(name) is True


def test_resolve_returns_the_real_path_for_a_benign_name(job_dir: Path) -> None:
    resolved = resolve_job_file(job_dir, "advisory.pdf")
    assert resolved is not None
    assert resolved == (job_dir / "advisory.pdf").resolve()


def test_resolve_allows_a_manifest_by_name(job_dir: Path) -> None:
    assert resolve_job_file(job_dir, "advisory.pdf.manifest.json") is not None


@pytest.mark.parametrize(
    "name", ["../../etc/passwd", "../job-2/secret.txt", "/etc/passwd", "a\x00b", "..", "sub/x"]
)
def test_resolve_refuses_to_escape_the_job_directory(job_dir: Path, name: str) -> None:
    assert resolve_job_file(job_dir, name) is None


def test_resolve_does_not_follow_a_symlink_pointing_outside(job_dir: Path, tmp_path: Path) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("classified", encoding="utf-8")
    (job_dir / "escape.txt").symlink_to(outside)
    assert resolve_job_file(job_dir, "escape.txt") is None


def test_resolve_allows_a_symlink_that_stays_inside(job_dir: Path) -> None:
    (job_dir / "alias.pdf").symlink_to(job_dir / "advisory.pdf")
    resolved = resolve_job_file(job_dir, "alias.pdf")
    assert resolved == (job_dir / "advisory.pdf").resolve()


def test_resolve_refuses_a_directory(job_dir: Path) -> None:
    (job_dir / "nested").mkdir()
    assert resolve_job_file(job_dir, "nested") is None


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no mkfifo on this platform")
def test_resolve_refuses_a_non_regular_file(job_dir: Path) -> None:
    os.mkfifo(job_dir / "pipe")
    assert resolve_job_file(job_dir, "pipe") is None


def test_resolve_returns_none_for_a_missing_file_or_directory(job_dir: Path) -> None:
    assert resolve_job_file(job_dir, "absent.pdf") is None
    assert resolve_job_file(job_dir.parent / "no-such-job", "advisory.pdf") is None


def test_job_files_excludes_manifests_and_symlinks(job_dir: Path, tmp_path: Path) -> None:
    (job_dir / "escape.txt").symlink_to(tmp_path / "elsewhere.txt")
    (job_dir / "nested").mkdir()
    assert [path.name for path in job_files(job_dir)] == ["advisory.md", "advisory.pdf"]


def test_job_files_is_empty_for_a_missing_directory(tmp_path: Path) -> None:
    assert job_files(tmp_path / "nope") == []
