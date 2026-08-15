"""`backend.ingestion.bbox` — 0-1000 normalized bbox -> pixel-box conversion.

docs/ingestion.md: bbox is `[ymin, xmin, ymax, xmax]`, 0-1000 normalized
against the ORIGINAL high-resolution page render. Model output is untrusted,
so out-of-range/inverted/degenerate boxes must still clamp to a valid,
non-empty crop box instead of raising.
"""

from PIL import Image

from backend.ingestion.bbox import bbox_to_pixels, crop_image


def test_bbox_center_box_converts_proportionally() -> None:
    # A box covering the middle half of a 1000x800 image on both axes.
    box = bbox_to_pixels([250, 250, 750, 750], width=1000, height=800)
    assert box == (250, 200, 750, 600)


def test_bbox_full_page_maps_to_full_image() -> None:
    box = bbox_to_pixels([0, 0, 1000, 1000], width=640, height=480)
    assert box == (0, 0, 640, 480)


def test_bbox_negative_and_over_1000_values_clamp_into_range() -> None:
    box = bbox_to_pixels([-50, -100, 1200, 1500], width=200, height=100)
    left, top, right, bottom = box
    assert 0 <= left < right <= 200
    assert 0 <= top < bottom <= 100
    # clamped to the full image since the input covers-and-exceeds it
    assert (left, top, right, bottom) == (0, 0, 200, 100)


def test_bbox_inverted_min_max_still_yields_nonempty_box() -> None:
    # ymax < ymin and xmax < xmin — a genuinely malformed model response.
    box = bbox_to_pixels([800, 800, 200, 200], width=1000, height=1000)
    left, top, right, bottom = box
    assert right > left
    assert bottom > top


def test_bbox_degenerate_zero_area_box_still_yields_one_pixel() -> None:
    box = bbox_to_pixels([500, 500, 500, 500], width=1000, height=1000)
    left, top, right, bottom = box
    assert right - left == 1
    assert bottom - top == 1


def test_bbox_degenerate_box_at_bottom_right_edge_clamps_inward() -> None:
    # A zero-area box sitting exactly at the bottom-right corner: clamping
    # forward would push it out of bounds, so it must clamp backward instead.
    box = bbox_to_pixels([1000, 1000, 1000, 1000], width=100, height=100)
    left, top, right, bottom = box
    assert 0 <= left < right <= 100
    assert 0 <= top < bottom <= 100
    assert (left, top, right, bottom) == (99, 99, 100, 100)


def test_crop_image_extracts_the_requested_pixel_box() -> None:
    image = Image.new("RGB", (100, 50), color=(10, 20, 30))
    cropped = crop_image(image, (10, 5, 40, 25))
    assert cropped.size == (30, 20)
