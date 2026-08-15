"""0-1000 normalized bbox -> pixel-box conversion and cropping (docs/ingestion.md 圖表裁切).

Vision models return figure boxes in the Gemini convention: `[ymin, xmin,
ymax, xmax]`, each 0-1000 normalized against the image's own height/width.
This module converts that back to a pixel box against the ORIGINAL
high-resolution page render (never a downscaled copy — cropping a thumbnail
would lose the quality the whole point of high-DPI rendering was for) and
crops it with Pillow.

Model output is untrusted: a box may be out of range, inverted, or
degenerate. `bbox_to_pixels` always returns a valid, clamped, non-empty
`(left, top, right, bottom)` box so `crop_image` never raises.
"""

from PIL.Image import Image

PixelBox = tuple[int, int, int, int]


def _scale_clamped(value: int, dimension: int) -> int:
    """Scale a 0-1000 normalized coordinate to a pixel coordinate, clamped to `[0, dimension]`."""
    pixel = round(value / 1000 * dimension)
    return max(0, min(dimension, pixel))


def bbox_to_pixels(bbox: list[int], *, width: int, height: int) -> PixelBox:
    """Convert a `[ymin, xmin, ymax, xmax]` 0-1000 bbox to a pixel box.

    Guarantees `0 <= left < right <= width` and `0 <= top < bottom <= height`
    (at least 1px wide/tall) so the result is always a valid Pillow crop box,
    even if the model returned an inverted or degenerate box.
    """
    ymin, xmin, ymax, xmax = bbox

    left = _scale_clamped(xmin, width)
    right = _scale_clamped(xmax, width)
    top = _scale_clamped(ymin, height)
    bottom = _scale_clamped(ymax, height)

    if right <= left:
        right = min(width, left + 1)
        if right <= left:  # left was already at `width`
            left = max(0, right - 1)
    if bottom <= top:
        bottom = min(height, top + 1)
        if bottom <= top:  # top was already at `height`
            top = max(0, bottom - 1)

    return left, top, right, bottom


def crop_image(image: Image, box: PixelBox) -> Image:
    """Crop `image` (the original full-resolution page render) to `box`."""
    return image.crop(box)
