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

    text = _normalize_text(file_path.read_text(encoding="utf-8", errors="ignore"))
    return [{"page_number": 1, "text": text}]
