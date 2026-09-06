"""Text extraction from pdf/docx/html/md/txt. Heavy parsers import inside the function (INV-3)."""

from __future__ import annotations

from pathlib import Path

from rupantar.core.schemas import TextBlock

_PLAIN = {".md", ".markdown", ".txt"}


def extract_text(path: Path) -> tuple[str, list[str]]:
    """Return (text, warnings) for one textual source; never raise on a parse failure."""
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            return _from_pdf(path), []
        if suffix == ".docx":
            return _from_docx(path), []
        if suffix in (".html", ".htm"):
            return _from_html(path), []
        if suffix in _PLAIN:
            return path.read_text(encoding="utf-8", errors="replace"), []
    except Exception as exc:  # noqa: BLE001 - a bad file is a warning, not a crash
        return "", [f"could not extract text from {path.name}: {type(exc).__name__}: {exc}"]
    return "", [f"unsupported text type: {suffix or path.name}"]


def text_block(path: Path) -> tuple[TextBlock | None, list[str]]:
    """Wrap `extract_text` into a TextBlock; None plus a warning when the text is empty."""
    text, warnings = extract_text(path)
    if not text.strip():
        return None, warnings or [f"no readable text in {path.name}"]
    return TextBlock(source_name=path.name, text=text.strip()), warnings


def _from_pdf(path: Path) -> str:
    """Concatenate the extracted text of every PDF page."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(part.strip() for part in pages if part.strip())


def _from_docx(path: Path) -> str:
    """Join every non-empty paragraph of a Word document."""
    import docx

    document = docx.Document(str(path))
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def _from_html(path: Path) -> str:
    """Strip script/style nodes and return the visible text of an HTML document."""
    from selectolax.parser import HTMLParser

    tree = HTMLParser(path.read_text(encoding="utf-8", errors="replace"))
    for node in tree.css("script, style"):
        node.decompose()
    body = tree.body or tree.root
    return body.text(separator=" ", strip=True) if body is not None else ""
