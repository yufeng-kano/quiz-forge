"""`backend.ingestion.chunking` — heading-structure + length-limited Markdown splitting."""

import pytest

from backend.ingestion.chunking import split_markdown_into_chunks


def test_empty_markdown_returns_no_chunks() -> None:
    assert split_markdown_into_chunks("   \n\n  ", max_chars=1000) == []


def test_markdown_with_no_headings_and_within_limit_is_one_chunk() -> None:
    markdown = "只是一段沒有標題的內文，長度很短。"
    chunks = split_markdown_into_chunks(markdown, max_chars=1000)
    assert chunks == [markdown]


def test_splits_on_heading_boundaries() -> None:
    markdown = (
        "# 光合作用\n\n光合作用發生在葉綠體。\n\n# 呼吸作用\n\n呼吸作用發生在粒線體。"
    )
    chunks = split_markdown_into_chunks(markdown, max_chars=1000)
    assert len(chunks) == 2
    assert chunks[0].startswith("# 光合作用")
    assert "光合作用發生在葉綠體" in chunks[0]
    assert chunks[1].startswith("# 呼吸作用")
    assert "呼吸作用發生在粒線體" in chunks[1]


def test_preamble_before_first_heading_becomes_its_own_chunk() -> None:
    markdown = "這是標題前的前言段落。\n\n# 第一節\n\n第一節內容。"
    chunks = split_markdown_into_chunks(markdown, max_chars=1000)
    assert len(chunks) == 2
    assert chunks[0] == "這是標題前的前言段落。"
    assert chunks[1].startswith("# 第一節")


def test_section_over_limit_is_split_by_paragraph() -> None:
    paragraph_a = "段落一內容。" * 5  # well within max_chars alone
    paragraph_b = "段落二內容。" * 5
    markdown = f"# 標題\n\n{paragraph_a}\n\n{paragraph_b}"
    # max_chars small enough that both paragraphs together overflow but each
    # paragraph alone (plus the heading) fits.
    max_chars = len(f"# 標題\n\n{paragraph_a}") + 5
    chunks = split_markdown_into_chunks(markdown, max_chars=max_chars)
    assert len(chunks) == 2
    assert all(len(chunk) <= max_chars for chunk in chunks)
    assert paragraph_a in chunks[0]
    assert paragraph_b in chunks[1]


def test_single_paragraph_longer_than_limit_is_hard_split() -> None:
    long_paragraph = "字" * 250  # CJK text, no spaces to break on
    chunks = split_markdown_into_chunks(long_paragraph, max_chars=100)
    assert len(chunks) == 3  # 100 + 100 + 50
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert "".join(chunks) == long_paragraph


def test_no_chunk_ever_exceeds_max_chars_for_mixed_content() -> None:
    markdown = (
        "# 一\n\n" + ("內容甲。" * 40) + "\n\n# 二\n\n" + ("內容乙。" * 3) + "\n\n"
        "# 三\n\n" + ("字" * 300)
    )
    max_chars = 120
    chunks = split_markdown_into_chunks(markdown, max_chars=max_chars)
    assert chunks  # non-empty
    assert all(len(chunk) <= max_chars for chunk in chunks)
    assert all(chunk.strip() for chunk in chunks)  # never an empty/blank chunk


def test_max_chars_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_chars must be positive"):
        split_markdown_into_chunks("內容", max_chars=0)
