"""`backend.ingestion.web.derive_webpage_title` — the fallback chain for a
網址（網頁）document's title (metadata title -> decoded URL path segment ->
hostname), plus the length cap. Regression coverage for the bug where the
webpage branch always kept `documents.title` as the raw, often
percent-encoded URL (see `test_ingestion_pipeline_url_file.py` /
`test_ingestion_classification.py` for the surrounding pipeline behaviour;
this file is pure-function coverage of the derivation itself, no network or
DB involved)."""

from backend.ingestion.web import derive_webpage_title

# ---------------------------------------------------------------------------
# 1) metadata title present -> always wins
# ---------------------------------------------------------------------------


def test_uses_metadata_title_when_present() -> None:
    title = derive_webpage_title(
        "https://blog.test/posts/%E5%85%89%E5%90%88%E4%BD%9C%E7%94%A8",
        metadata_title="光合作用完整教學",
        max_length=200,
    )
    assert title == "光合作用完整教學"


def test_strips_whitespace_around_metadata_title() -> None:
    title = derive_webpage_title(
        "https://blog.test/post", metadata_title="  有空白的標題  ", max_length=200
    )
    assert title == "有空白的標題"


def test_blank_metadata_title_falls_through_to_url_path() -> None:
    title = derive_webpage_title(
        "https://blog.test/posts/photosynthesis", metadata_title="   ", max_length=200
    )
    assert title == "photosynthesis"


# ---------------------------------------------------------------------------
# 2) no metadata title -> decoded last URL path segment
# ---------------------------------------------------------------------------


def test_falls_back_to_percent_decoded_last_path_segment_when_no_metadata_title() -> None:
    # This is exactly the production bug report: a percent-encoded Chinese
    # slug must render as real text, not `%E8%A7...` gibberish.
    title = derive_webpage_title(
        "https://blog.test/posts/%E5%85%89%E5%90%88%E4%BD%9C%E7%94%A8",
        metadata_title=None,
        max_length=200,
    )
    assert title == "光合作用"


def test_falls_back_to_last_segment_ignoring_trailing_slash() -> None:
    title = derive_webpage_title(
        "https://blog.test/posts/photosynthesis/", metadata_title=None, max_length=200
    )
    assert title == "photosynthesis"


def test_falls_back_to_last_segment_of_multi_level_path() -> None:
    title = derive_webpage_title(
        "https://blog.test/2026/08/photosynthesis-basics",
        metadata_title=None,
        max_length=200,
    )
    assert title == "photosynthesis-basics"


# ---------------------------------------------------------------------------
# 3) no metadata title, no path -> bare hostname
# ---------------------------------------------------------------------------


def test_falls_back_to_hostname_when_url_has_no_path() -> None:
    title = derive_webpage_title("https://blog.test", metadata_title=None, max_length=200)
    assert title == "blog.test"


def test_falls_back_to_hostname_when_url_path_is_only_slashes() -> None:
    title = derive_webpage_title("https://blog.test///", metadata_title=None, max_length=200)
    assert title == "blog.test"


# ---------------------------------------------------------------------------
# length cap — applies regardless of which branch produced the title
# ---------------------------------------------------------------------------


def test_metadata_title_is_capped_at_max_length() -> None:
    title = derive_webpage_title(
        "https://blog.test/post", metadata_title="A" * 300, max_length=50
    )
    assert title == "A" * 50


def test_path_segment_title_is_capped_at_max_length() -> None:
    title = derive_webpage_title(
        f"https://blog.test/{'a' * 300}", metadata_title=None, max_length=50
    )
    assert title == "a" * 50


def test_hostname_title_is_capped_at_max_length() -> None:
    long_host = "sub." * 60 + "test"
    title = derive_webpage_title(f"https://{long_host}", metadata_title=None, max_length=50)
    assert title == long_host[:50]
