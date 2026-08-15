"""`backend.ingestion.vision` — response schema validation + placeholder rewriting."""

import pytest
from pydantic import ValidationError

from backend.ingestion.vision import Figure, VisionPageResult, rewrite_figure_placeholders


def test_figure_rejects_bbox_with_wrong_length() -> None:
    with pytest.raises(ValidationError):
        Figure(id="fig-1", bbox=[0, 0, 1000], caption="不完整的 bbox")


def test_vision_page_result_parses_full_shape() -> None:
    result = VisionPageResult.model_validate(
        {
            "markdown": "# 標題\n\n內文 ![fig-1] 之後的段落。",
            "figures": [
                {"id": "fig-1", "bbox": [100, 200, 300, 400], "caption": "示意圖"},
            ],
        }
    )
    assert result.figures[0].bbox == [100, 200, 300, 400]


def test_rewrite_figure_placeholders_replaces_bare_placeholder() -> None:
    markdown = "前言\n\n![fig-1]\n\n後記"
    result = rewrite_figure_placeholders(markdown, {"fig-1": "![圖說](/api/v1/assets/42)"})
    assert result == "前言\n\n![圖說](/api/v1/assets/42)\n\n後記"


def test_rewrite_figure_placeholders_replaces_multiple_distinct_ids() -> None:
    markdown = "A ![fig-1] B ![fig-2] C"
    result = rewrite_figure_placeholders(
        markdown,
        {
            "fig-1": "![第一圖](/api/v1/assets/1)",
            "fig-2": "![第二圖](/api/v1/assets/2)",
        },
    )
    assert result == "A ![第一圖](/api/v1/assets/1) B ![第二圖](/api/v1/assets/2) C"


def test_rewrite_figure_placeholders_tolerates_model_added_parens() -> None:
    # A model that (against instructions) already turned the placeholder into
    # valid-looking Markdown image syntax with a bogus URL/empty parens.
    markdown = "見 ![fig-1](some-bogus-url) 圖"
    result = rewrite_figure_placeholders(markdown, {"fig-1": "![圖說](/api/v1/assets/9)"})
    assert result == "見 ![圖說](/api/v1/assets/9) 圖"


def test_rewrite_figure_placeholders_leaves_unmatched_ids_untouched() -> None:
    markdown = "只有 ![fig-1] 沒有 fig-2"
    result = rewrite_figure_placeholders(markdown, {"fig-1": "![圖說](/api/v1/assets/1)"})
    assert result == "只有 ![圖說](/api/v1/assets/1) 沒有 fig-2"


def test_rewrite_figure_placeholders_replacement_with_backslash_is_literal() -> None:
    # A caption/URL containing a backslash must never be misread as a regex
    # backreference by the underlying `re.sub` call.
    markdown = "![fig-1]"
    result = rewrite_figure_placeholders(markdown, {"fig-1": r"![C:\path\to\thing](url)"})
    assert result == r"![C:\path\to\thing](url)"
