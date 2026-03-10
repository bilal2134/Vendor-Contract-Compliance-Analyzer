from app.services.chunking import chunk_pages, detect_section_name


def test_detect_section_name_handles_alpha_number_headings() -> None:
    page_text = "B.4  PENETRATION TESTING\nExternal Penetration Test (Annual)"

    assert detect_section_name(page_text) == "B.4 PENETRATION TESTING"


def test_chunk_pages_keeps_header_with_following_answer_text() -> None:
    pages = [
        {
            "page_number": 1,
            "text": "\n".join(
                [
                    "SECTION B - SECURITY TESTING",
                    "Overview text " * 80,
                    "B.4  PENETRATION TESTING",
                    "External Penetration Test (Annual)",
                    "Performed by independent third party assessor.",
                    "Web Application Penetration Test (Semi-Annual)",
                    "F.1  Business Continuity Plan:",
                    'ANSWER: Yes - "NovaTech Business Continuity Plan v3.0" reviewed Jan 2026.',
                ]
            ),
        }
    ]

    chunks = chunk_pages(pages, max_chars=500, overlap=80)
    texts = [chunk["text"] for chunk in chunks]

    assert any(
        "B.4  PENETRATION TESTING" in text
        and "External Penetration Test (Annual)" in text
        for text in texts
    )
    assert any(
        "F.1  Business Continuity Plan:" in text
        and "NovaTech Business Continuity Plan v3.0" in text
        for text in texts
    )
    assert not any(text.strip() == "B.4  PENETRATION TESTING" for text in texts)