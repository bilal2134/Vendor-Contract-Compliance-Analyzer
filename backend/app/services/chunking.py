from __future__ import annotations

import re

HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
ALPHA_HEADING_RE = re.compile(r"^([A-Z]\.\d+(?:\.\d+)*)\s+(.+)$")
SECTION_HEADING_RE = re.compile(r"^SECTION\s+[A-Z0-9].+$", re.IGNORECASE)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "must", "shall", "will", "into",
    "have", "has", "are", "not", "any", "all", "but", "its", "their", "your", "than",
}


def _is_heading_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if HEADING_RE.match(stripped) or ALPHA_HEADING_RE.match(stripped):
        return True
    if SECTION_HEADING_RE.match(stripped):
        return True
    return stripped.isupper() and len(stripped.split()) <= 10


def _normalize_heading_line(line: str) -> str:
    stripped = line.strip()
    numeric_match = HEADING_RE.match(stripped)
    if numeric_match:
        return f"{numeric_match.group(1)} {numeric_match.group(2).strip()}"
    alpha_match = ALPHA_HEADING_RE.match(stripped)
    if alpha_match:
        return f"{alpha_match.group(1)} {alpha_match.group(2).strip()}"
    if stripped.isupper() and len(stripped.split()) <= 10:
        return stripped.title()
    return stripped


def _split_heading_blocks(page_text: str) -> list[tuple[str | None, list[str]]]:
    blocks: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for raw_line in page_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _is_heading_line(line):
            if current_lines:
                blocks.append((current_heading, current_lines))
            current_heading = _normalize_heading_line(line)
            current_lines = [line]
            continue
        if not current_lines:
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        blocks.append((current_heading, current_lines))
    return blocks


def detect_section_name(page_text: str) -> str | None:
    for raw_line in page_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _is_heading_line(line):
            return _normalize_heading_line(line)
    return None


def chunk_pages(pages: list[dict], max_chars: int = 1400, overlap: int = 240) -> list[dict]:
    chunks: list[dict] = []
    chunk_index = 0
    for page in pages:
        page_text = page["text"].strip()
        if not page_text:
            continue
        default_section_name = detect_section_name(page_text)
        blocks = _split_heading_blocks(page_text)
        if not blocks:
            blocks = [(default_section_name, [page_text])]

        for block_heading, block_lines in blocks:
            section_name = block_heading or default_section_name
            if not block_lines:
                continue

            start_line = 0
            while start_line < len(block_lines):
                chunk_lines: list[str] = []
                content_lines = 0
                content_words = 0
                line_index = start_line
                while line_index < len(block_lines):
                    candidate_lines = chunk_lines + [block_lines[line_index]]
                    candidate_text = "\n".join(candidate_lines).strip()
                    force_attach_body = (
                        start_line == 0
                        and content_lines < 2
                        and content_words < 120
                    )
                    if chunk_lines and len(candidate_text) > max_chars and not force_attach_body:
                        break
                    chunk_lines.append(block_lines[line_index])
                    if not _is_heading_line(block_lines[line_index]):
                        content_lines += 1
                        content_words += len(block_lines[line_index].split())
                    line_index += 1

                text = "\n".join(chunk_lines).strip()
                if text:
                    if section_name and not text.lower().startswith(section_name.lower()):
                        text = f"{section_name}\n{text}"
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

                if line_index >= len(block_lines):
                    break

                next_start = line_index
                overlap_chars = 0
                while next_start > start_line:
                    previous_line = block_lines[next_start - 1]
                    projected = overlap_chars + len(previous_line) + 1
                    if projected > overlap and next_start < line_index:
                        break
                    overlap_chars = projected
                    next_start -= 1
                start_line = max(start_line + 1, next_start)
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
