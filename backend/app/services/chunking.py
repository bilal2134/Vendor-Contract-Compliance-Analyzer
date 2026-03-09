from __future__ import annotations

import re

HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "must", "shall", "will", "into",
    "have", "has", "are", "not", "any", "all", "but", "its", "their", "your", "than",
}


def detect_section_name(page_text: str) -> str | None:
    for raw_line in page_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading_match = HEADING_RE.match(line)
        if heading_match:
            return f"{heading_match.group(1)} {heading_match.group(2).strip()}"
        if line.isupper() and len(line.split()) <= 8:
            return line.title()
    return None


def chunk_pages(pages: list[dict], max_chars: int = 1400, overlap: int = 240) -> list[dict]:
    chunks: list[dict] = []
    chunk_index = 0
    for page in pages:
        page_text = page["text"].strip()
        if not page_text:
            continue
        section_name = detect_section_name(page_text)
        start = 0
        while start < len(page_text):
            end = min(len(page_text), start + max_chars)
            if end < len(page_text):
                boundary = page_text.rfind(" ", start, end)
                if boundary > start + max_chars // 2:
                    end = boundary
            text = page_text[start:end].strip()
            if text:
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "page_number": page["page_number"],
                        "section_name": section_name,
                        "text": text,
                        "keywords": extract_keywords(text),
                    }
                )
                chunk_index += 1
            if end >= len(page_text):
                break
            start = max(0, end - overlap)
    return chunks


def extract_keywords(text: str, limit: int = 12) -> list[str]:
    counts: dict[str, int] = {}
    for token in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text.lower()):
        if token in STOPWORDS:
            continue
        counts[token] = counts.get(token, 0) + 1
    return [token for token, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def split_sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in SENTENCE_RE.split(text) if sentence.strip()]
