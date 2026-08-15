"""Vision-call response schema + figure-placeholder rewriting (docs/ingestion.md Vision 管線).

The vision call itself (`response_format: json_schema`, model `VISION_MODEL`)
is a thin use of `backend.llm.LLMClient.vision` — the logic worth its own
module and tests is (a) the strict output schema and (b) rewriting the
`![fig-N]` placeholders the model emits into real `/api/v1/assets/{id}`
image links once each figure has been cropped and saved.
"""

import re

from pydantic import BaseModel, field_validator


class Figure(BaseModel):
    """One figure the vision model located on the page."""

    id: str
    # [ymin, xmin, ymax, xmax], 0-1000 normalized — see docs/ingestion.md.
    bbox: list[int]
    caption: str

    @field_validator("bbox")
    @classmethod
    def _bbox_has_four_elements(cls, bbox: list[int]) -> list[int]:
        if len(bbox) != 4:
            raise ValueError(
                f"bbox must have exactly 4 elements [ymin, xmin, ymax, xmax], got {len(bbox)}"
            )
        return bbox


class VisionPageResult(BaseModel):
    """The exact `response_format: json_schema` shape for one page's vision call."""

    markdown: str
    figures: list[Figure]


def _placeholder_pattern(figure_id: str) -> re.Pattern[str]:
    # Matches the bare `![fig-1]` placeholder the prompt asks for, and also
    # tolerates the model accidentally emitting a trailing `(...)` group
    # (i.e. turning it into valid Markdown image syntax on its own).
    return re.compile(rf"!\[{re.escape(figure_id)}\](\([^)]*\))?")


def rewrite_figure_placeholders(markdown: str, replacements: dict[str, str]) -> str:
    """Replace each `![fig-N]` placeholder in `markdown` with `replacements[fig-N]`.

    `replacements` maps a figure id (`Figure.id`) to the full Markdown image
    snippet that should replace its placeholder — typically
    `![caption](/api/v1/assets/{asset_id})`. Placeholders with no matching
    entry in `replacements` are left untouched.
    """
    result = markdown
    for figure_id, replacement in replacements.items():
        # Use a callable replacement (not a raw string) so a caption/URL that
        # happens to contain backslashes is never misread as a regex
        # backreference by `re.sub`. The `replacement=replacement` default
        # binds *this* iteration's value instead of the loop variable cell.
        result = _placeholder_pattern(figure_id).sub(
            lambda _match, replacement=replacement: replacement, result
        )
    return result
