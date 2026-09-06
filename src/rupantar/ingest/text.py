"""Text extraction into TextBlocks. Heavy parsers import inside the function (INV-3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rupantar.core.schemas import TextBlock

_PLAIN = {".md", ".markdown", ".txt"}
_HTML = {".html", ".htm"}


def extract_blocks(path: Path) -> tuple[list[TextBlock], list[str]]:
    """Return (blocks, warnings) for one textual source; never raise on a parse failure."""
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            return _from_pdf(path)
        if suffix == ".docx":
            return _from_docx(path)
        if suffix in _HTML:
            return _one_block(path, _from_html(path))
        if suffix in _PLAIN:
            return _one_block(path, path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001 - a bad file is a warning, not a crash
        return [], [f"could not extract text from {path.name}: {type(exc).__name__}: {exc}"]
    return [], [f"unsupported text type: {suffix or path.name}"]


def extract_text(path: Path) -> tuple[str, list[str]]:
    """Joined text of every block for `path`; compatibility shim over `extract_blocks`."""
    blocks, warnings = extract_blocks(path)
    return "\n\n".join(block.text for block in blocks), warnings


def _one_block(path: Path, text: str) -> tuple[list[TextBlock], list[str]]:
    """Wrap one extracted string as a single TextBlock, or warn when it is empty."""
    if not text.strip():
        return [], [f"no readable text in {path.name}"]
    return [TextBlock(source_name=path.name, text=text.strip())], []


def _from_pdf(path: Path) -> tuple[list[TextBlock], list[str]]:
    """One TextBlock per non-empty page, tagged with its 1-based page and nearest heading."""
    import pymupdf

    blocks: list[TextBlock] = []
    with pymupdf.open(str(path)) as doc:
        for number, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if not text:
                continue
            blocks.append(
                TextBlock(
                    source_name=path.name,
                    text=text,
                    page=number,
                    heading=_page_heading(page),
                )
            )
    return blocks, []


def _page_heading(page: Any) -> str:
    """First short span on the page whose font is clearly above the body size or bold."""
    spans = _spans(page)
    if not spans:
        return ""
    sizes = sorted(span["size"] for span in spans)
    body = sizes[len(sizes) // 2]
    for span in spans:
        text = " ".join(span["text"].split())
        if not text or len(text) > 80:
            continue
        bold = bool(int(span.get("flags", 0)) & 16) or "bold" in str(span.get("font", "")).lower()
        if span["size"] >= body * 1.15 or bold:
            return text
    return ""


def _spans(page: Any) -> list[dict[str, Any]]:
    """Flatten every text span of a PyMuPDF page in reading order."""
    out: list[dict[str, Any]] = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            out.extend(line.get("spans", []))
    return out


def _from_docx(path: Path) -> tuple[list[TextBlock], list[str]]:
    """One TextBlock per Heading-delimited section, or a single block without headings."""
    import docx

    document = docx.Document(str(path))
    sections: list[TextBlock] = []
    heading = ""
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            sections.append(TextBlock(source_name=path.name, text=text, heading=heading))

    for para in document.paragraphs:
        style = (para.style.name if para.style is not None else "") or ""
        if style.startswith("Heading") and para.text.strip():
            flush()
            heading = para.text.strip()
            buffer = []
        elif para.text.strip():
            buffer.append(para.text)
    flush()
    if not sections:
        return [], [f"no readable text in {path.name}"]
    return sections, []


def _from_html(path: Path) -> str:
    """Strip script/style nodes and return the visible text of an HTML document."""
    from selectolax.parser import HTMLParser

    tree = HTMLParser(path.read_text(encoding="utf-8", errors="replace"))
    for node in tree.css("script, style"):
        node.decompose()
    body = tree.body or tree.root
    return body.text(separator=" ", strip=True) if body is not None else ""
