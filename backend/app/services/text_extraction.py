from __future__ import annotations

import re
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


WHITESPACE_RE = re.compile(r"\s+")


def _normalize_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value.replace("\x00", " ")).strip()


def extract_text_pages(file_path: Path) -> list[dict]:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(file_path))
        pages: list[dict] = []
        for index, page in enumerate(reader.pages, start=1):
            page_text = _normalize_text(page.extract_text() or "")
            pages.append({"page_number": index, "text": page_text})
        return pages

    if suffix == ".docx":
        document = DocxDocument(str(file_path))
        paragraphs = [_normalize_text(paragraph.text) for paragraph in document.paragraphs if paragraph.text.strip()]
        return [{"page_number": 1, "text": "\n".join(paragraphs)}]

    # Preserve line structure for section-heading detection.
    # Split at 2+ blank lines so each article/section becomes a separate "page".
    text_raw = file_path.read_text(encoding="utf-8", errors="ignore").replace("\x00", "")
    raw_sections = re.split(r"\n{2,}", text_raw)
    pages: list[dict] = []
    for i, section in enumerate(raw_sections, start=1):
        cleaned = re.sub(r"[^\S\n]+", " ", section).strip()
        if cleaned:
            pages.append({"page_number": i, "text": cleaned})
    return pages if pages else [{"page_number": 1, "text": _normalize_text(text_raw)}]
