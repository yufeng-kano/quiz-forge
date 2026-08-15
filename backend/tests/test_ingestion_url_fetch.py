"""`backend.ingestion.url_fetch` — docs/ingestion.md 網址（檔案） row.

`classify_url_content` is a pure function (the content-type/extension
routing decision table) tested with no network at all. `probe_content_type`
and `download_url_file` do real blocking HTTP against a throwaway
`http.server.ThreadingHTTPServer` bound to `127.0.0.1` on this test process
— a real socket, real headers, real streaming download and size-cap abort,
not a mocked HTTP layer.
"""

from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from backend.ingestion.url_fetch import (
    UnsupportedUrlContentError,
    UrlFetchError,
    UrlFetchTooLargeError,
    classify_url_content,
    derive_filename,
    download_url_file,
    probe_content_type,
)

# ---------------------------------------------------------------------------
# classify_url_content — pure routing decision table, no network involved.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("content_type", "url", "expected_kind"),
    [
        ("application/pdf", "https://x.test/report", "pdf"),
        ("application/pdf; charset=binary", "https://x.test/report", "pdf"),
        ("APPLICATION/PDF", "https://x.test/report", "pdf"),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "https://x.test/notes",
            "word",
        ),
        ("image/png", "https://x.test/scan", "image"),
        ("image/jpeg", "https://x.test/scan", "image"),
        ("text/html", "https://x.test/article", None),
        ("text/html; charset=utf-8", "https://x.test/article", None),
        ("application/xhtml+xml", "https://x.test/article", None),
        (None, "https://x.test/blog/post", None),  # no signal at all -> web page
        ("text/plain", "https://x.test/data.txt", None),  # generic text/* -> web page
        # generic/missing content-type -> fall back to the URL's own extension
        (None, "https://x.test/download/report.pdf", "pdf"),
        ("application/octet-stream", "https://cdn.test/files/report.pdf", "pdf"),
        ("application/octet-stream", "https://cdn.test/files/notes.docx", "word"),
        ("binary/octet-stream", "https://cdn.test/files/scan.PNG", "image"),
    ],
)
def test_classify_url_content_decision_table(
    content_type: str | None, url: str, expected_kind: str | None
) -> None:
    assert classify_url_content(content_type, url) == expected_kind


@pytest.mark.parametrize(
    ("content_type", "url"),
    [
        ("application/zip", "https://x.test/archive.zip"),
        ("video/mp4", "https://x.test/clip.mp4"),
        # generic binary content-type with no usable extension to fall back on
        ("application/octet-stream", "https://x.test/download"),
    ],
)
def test_classify_url_content_rejects_unsupported_types(content_type: str, url: str) -> None:
    with pytest.raises(UnsupportedUrlContentError):
        classify_url_content(content_type, url)


# ---------------------------------------------------------------------------
# derive_filename
# ---------------------------------------------------------------------------


def test_derive_filename_keeps_url_filename_when_extension_matches_kind() -> None:
    assert derive_filename("https://x.test/files/report.pdf", "pdf") == "report.pdf"


def test_derive_filename_builds_canonical_extension_when_url_has_none() -> None:
    assert derive_filename("https://x.test/download?id=42", "pdf") == "download.pdf"


def test_derive_filename_replaces_mismatched_extension_with_canonical_one() -> None:
    # e.g. a URL whose path extension didn't match the kind actually
    # resolved by content-type/extension fallback.
    assert derive_filename("https://x.test/files/report.bin", "word") == "report.docx"


def test_derive_filename_falls_back_to_hostname_when_url_has_no_path() -> None:
    assert derive_filename("https://cdn.example.test", "image") == "cdn.example.test.png"


# ---------------------------------------------------------------------------
# probe_content_type / download_url_file — real HTTP against a local server.
# ---------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
        pass  # keep test output quiet

    def _body_for(self, path: str) -> tuple[int, str, bytes]:
        if path == "/file.pdf":
            return 200, "application/pdf", b"%PDF-1.4 fake pdf body"
        if path == "/big.bin":
            return 200, "application/pdf", b"x" * (64 * 1024)
        if path == "/page.html":
            return 200, "text/html; charset=utf-8", b"<html><body>hi</body></html>"
        if path == "/head-not-allowed":
            return 200, "application/pdf", b"%PDF-1.4 no head support"
        return 404, "text/plain", b"not found"

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib method name
        if self.path == "/head-not-allowed":
            self.send_response(405)
            self.end_headers()
            return
        status, content_type, body = self._body_for(self.path)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        status, content_type, body = self._body_for(self.path)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def local_server() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


def test_probe_content_type_uses_head_when_supported(local_server: str) -> None:
    content_type, final_url = probe_content_type(f"{local_server}/file.pdf", timeout=5.0)
    assert content_type == "application/pdf"
    assert final_url == f"{local_server}/file.pdf"


def test_probe_content_type_falls_back_to_get_when_head_rejected(local_server: str) -> None:
    content_type, _final_url = probe_content_type(f"{local_server}/head-not-allowed", timeout=5.0)
    assert content_type == "application/pdf"


def test_probe_content_type_raises_for_unreachable_host() -> None:
    with pytest.raises(UrlFetchError):
        probe_content_type("http://127.0.0.1:1/does-not-exist", timeout=1.0)


def test_download_url_file_streams_exact_bytes(local_server: str) -> None:
    data = download_url_file(f"{local_server}/file.pdf", max_bytes=10_000, timeout=5.0)
    assert data == b"%PDF-1.4 fake pdf body"


def test_download_url_file_aborts_once_max_bytes_exceeded(local_server: str) -> None:
    with pytest.raises(UrlFetchTooLargeError, match="URL_FETCH_MAX_BYTES"):
        download_url_file(f"{local_server}/big.bin", max_bytes=1024, timeout=5.0)


def test_download_url_file_raises_for_unreachable_host() -> None:
    with pytest.raises(UrlFetchError):
        download_url_file("http://127.0.0.1:1/does-not-exist", max_bytes=1024, timeout=1.0)
