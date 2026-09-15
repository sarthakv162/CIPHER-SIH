"""Template selection in render_pptx/render_docx: real templates, and every fallback branch."""

from __future__ import annotations

from pathlib import Path

from rupantar.core.artefacts import Advisory, Presentation
from rupantar.render.context import RenderContext
from rupantar.render.docx_render import render_docx
from rupantar.render.pptx_render import render_pptx


def _load(model: type, artefacts_dir: Path, name: str):  # type: ignore[no-untyped-def]
    return model.model_validate_json((artefacts_dir / f"{name}.json").read_text())


def _manifest(tmp_path: Path, body: str) -> Path:
    directory = tmp_path / "templates"
    directory.mkdir(exist_ok=True)
    (directory / "templates.yaml").write_text(body, encoding="utf-8")
    return tmp_path


def test_each_shipped_template_renders_a_pptx_with_no_warnings(
    artefacts_dir: Path, tmp_path: Path
) -> None:
    presentation = _load(Presentation, artefacts_dir, "presentation")
    for template_id in ("ntro-formal", "executive", "technical"):
        context = RenderContext(template_id=template_id)
        render_pptx(presentation, tmp_path / f"{template_id}.pptx", context=context)
        assert context.warnings == []
        assert (tmp_path / f"{template_id}.pptx").is_file()


def test_each_shipped_template_renders_a_docx_with_no_warnings(
    artefacts_dir: Path, tmp_path: Path
) -> None:
    advisory = _load(Advisory, artefacts_dir, "advisory")
    for template_id in ("ntro-formal", "executive", "technical"):
        context = RenderContext(template_id=template_id)
        render_docx(advisory, tmp_path / f"{template_id}.docx", context=context)
        assert context.warnings == []
        assert (tmp_path / f"{template_id}.docx").is_file()


def test_unknown_template_id_falls_back_with_a_warning(artefacts_dir: Path, tmp_path: Path) -> None:
    presentation = _load(Presentation, artefacts_dir, "presentation")
    context = RenderContext(template_id="does-not-exist")
    render_pptx(presentation, tmp_path / "out.pptx", context=context)
    assert any("does-not-exist" in w for w in context.warnings)
    assert (tmp_path / "out.pptx").is_file()


def test_template_with_no_pptx_binding_falls_back_with_a_warning(
    artefacts_dir: Path, tmp_path: Path
) -> None:
    configs_dir = _manifest(
        tmp_path,
        "templates:\n  - id: docx-only\n    label: Docx Only\n    docx: {file: x.dotx}\n",
    )
    presentation = _load(Presentation, artefacts_dir, "presentation")
    context = RenderContext(template_id="docx-only", configs_dir=configs_dir)
    render_pptx(presentation, tmp_path / "out.pptx", context=context)
    assert any("no pptx binding" in w for w in context.warnings)


def test_template_pointing_at_a_missing_potx_falls_back_with_a_warning(
    artefacts_dir: Path, tmp_path: Path
) -> None:
    configs_dir = _manifest(
        tmp_path,
        "templates:\n  - id: ghost\n    label: Ghost\n"
        "    pptx: {file: nowhere.potx, layouts: {title_slide: 0, title: 2, bullets: 1, "
        "two_column: 3, quote: 1, closing: 2}}\n",
    )
    presentation = _load(Presentation, artefacts_dir, "presentation")
    context = RenderContext(template_id="ghost", configs_dir=configs_dir)
    render_pptx(presentation, tmp_path / "out.pptx", context=context)
    assert any("is missing" in w for w in context.warnings)


def test_template_pointing_at_a_corrupt_potx_falls_back_with_a_warning(
    artefacts_dir: Path, tmp_path: Path
) -> None:
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "broken.potx").write_bytes(b"not a real pptx file")
    configs_dir = _manifest(
        tmp_path,
        "templates:\n  - id: broken\n    label: Broken\n"
        "    pptx: {file: broken.potx, layouts: {title_slide: 0, title: 2, bullets: 1, "
        "two_column: 3, quote: 1, closing: 2}}\n",
    )
    presentation = _load(Presentation, artefacts_dir, "presentation")
    context = RenderContext(template_id="broken", configs_dir=configs_dir)
    render_pptx(presentation, tmp_path / "out.pptx", context=context)
    assert any("could not be opened" in w for w in context.warnings)
    assert (tmp_path / "out.pptx").is_file()


def test_out_of_range_layout_index_falls_back_to_the_nearest_one(
    artefacts_dir: Path, tmp_path: Path
) -> None:
    configs_dir = _manifest(
        tmp_path,
        "templates:\n  - id: ntro-formal\n    label: NTRO\n"
        "    pptx: {file: ntro-formal.potx, layouts: {title_slide: 0, title: 2, bullets: 1, "
        "two_column: 999, quote: 1, closing: 2}}\n",
    )
    # Reuse the real shipped .potx so the file itself opens fine; only its layout map is bad.
    real_configs = Path(__file__).resolve().parents[2] / "configs"
    (configs_dir / "templates" / "ntro-formal.potx").write_bytes(
        (real_configs / "templates" / "ntro-formal.potx").read_bytes()
    )
    presentation = _load(Presentation, artefacts_dir, "presentation")
    context = RenderContext(template_id="ntro-formal", configs_dir=configs_dir)
    render_pptx(presentation, tmp_path / "out.pptx", context=context)
    assert any("two_column" in w and "out of range" in w for w in context.warnings)


def test_docx_style_name_not_in_the_template_falls_back_with_a_warning(
    artefacts_dir: Path, tmp_path: Path
) -> None:
    configs_dir = _manifest(
        tmp_path,
        "templates:\n  - id: bad-style\n    label: Bad Style\n"
        "    docx: {file: bad.dotx, styles: {heading1: 'Not A Real Style'}}\n",
    )
    real_configs = Path(__file__).resolve().parents[2] / "configs"
    (configs_dir / "templates" / "bad.dotx").write_bytes(
        (real_configs / "templates" / "ntro-formal.dotx").read_bytes()
    )
    advisory = _load(Advisory, artefacts_dir, "advisory")
    context = RenderContext(template_id="bad-style", configs_dir=configs_dir)
    render_docx(advisory, tmp_path / "out.docx", context=context)
    assert any("heading1" in w and "not found" in w for w in context.warnings)


def test_no_context_reproduces_the_pre_template_default_output(
    artefacts_dir: Path, tmp_path: Path
) -> None:
    presentation = _load(Presentation, artefacts_dir, "presentation")
    advisory = _load(Advisory, artefacts_dir, "advisory")
    render_pptx(presentation, tmp_path / "no_context.pptx")
    render_docx(advisory, tmp_path / "no_context.docx")
    assert (tmp_path / "no_context.pptx").is_file()
    assert (tmp_path / "no_context.docx").is_file()
