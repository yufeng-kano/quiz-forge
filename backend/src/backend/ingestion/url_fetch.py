"""URL routing + file download for `source_type=url` documents
(docs/ingestion.md — 網址（檔案） row).

A `POST /v1/documents/url` request only knows the URL up front; whether it
actually points at a downloadable file (PDF/Word/image) or an HTML page
can only be decided once the response headers come back. This module owns
that decision (`classify_url_content`, a pure function so the routing table
is directly unit-testable) plus the streaming download itself
(`download_url_file`), capped at `Settings.url_fetch_max_bytes` so a link to
a huge file can't exhaust disk/memory.

The web-page branch (docs/ingestion.md 網址（網頁）) is untouched by this
module — once `classify_url_content` returns `None`, the caller (
`backend.ingestion.pipeline`) falls through to the existing
`web.fetch_html`/`web.extract_main_content` path exactly as before this
feature existed.

Every function here does blocking network I/O — callers must run them via
`asyncio.to_thread`, same convention as `backend.ingestion.web`.
"""

from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from backend.ingestion.kind import UnsupportedUploadError, UploadKind, detect_upload_kind

_USER_AGENT = "quiz-forge/1.0 (+https://github.com/)"
_CHUNK_SIZE = 65536

# content-type -> UploadKind, kept separate from `kind.py`'s extension table
# (a response's Content-Type and a URL's path extension are independent
# signals — docs/ingestion.md 依 content-type／副檔名判斷 — either one alone
# is enough to route to the file pipeline).
_CONTENT_TYPE_KIND: dict[str, UploadKind] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word",
    "image/png": "image",
    "image/jpeg": "image",
}

_HTML_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}

_CANONICAL_EXTENSION: dict[UploadKind, str] = {"pdf": ".pdf", "word": ".docx", "image": ".png"}


class UrlFetchError(RuntimeError):
    """Raised when a URL can't be reached at all (DNS/connection/timeout/HTTP error)."""


class UnsupportedUrlContentError(ValueError):
    """Raised when a URL's response is neither a supported file kind nor HTML."""


class UrlFetchTooLargeError(RuntimeError):
    """Raised when a URL file download exceeds `Settings.url_fetch_max_bytes`."""


def _normalize_content_type(content_type: str | None) -> str | None:
    if content_type is None:
        return None
    return content_type.split(";", 1)[0].strip().lower() or None


def classify_url_content(content_type: str | None, url: str) -> UploadKind | None:
    """Decide whether `url` (given its response `content_type`) is a
    supported file kind, or a web page (returned as `None`).

    content-type is checked first; the URL path's extension (via the same
    table `kind.detect_upload_kind` uses for uploads) is the fallback for
    servers that send a generic/missing content-type for file downloads
    (docs/ingestion.md 依 content-type／副檔名判斷). Anything that is
    neither a recognized file kind, HTML, nor extractable via the fallbacks
    raises `UnsupportedUrlContentError` with a clear, localizable-ready
    message.
    """
    normalized = _normalize_content_type(content_type)

    if normalized is not None:
        file_kind = _CONTENT_TYPE_KIND.get(normalized)
        if file_kind is not None:
            return file_kind
        if normalized in _HTML_CONTENT_TYPES:
            return None

    path_name = Path(urlparse(url).path).name
    if path_name:
        try:
            return detect_upload_kind(path_name)
        except UnsupportedUploadError:
            pass

    if normalized is None or normalized.startswith("text/"):
        # No usable file signal at all (missing header, or a generic
        # text/* type) — behave exactly as before this feature existed:
        # hand off to the trafilatura web-page path, which raises its own
        # clear error if the content truly isn't extractable.
        return None

    supported = ", ".join(sorted({*_CONTENT_TYPE_KIND, *_HTML_CONTENT_TYPES}))
    raise UnsupportedUrlContentError(
        f"unsupported content-type {content_type!r} for URL {url!r}; supported: {supported}"
    )


def probe_content_type(url: str, timeout: float) -> tuple[str | None, str]:
    """One lightweight request (HEAD, falling back to GET if the server
    rejects HEAD) to learn `url`'s actual `Content-Type` and final
    (post-redirect) URL, without downloading a file's body — the routing
    decision needs the header before deciding whether to stream a file
    download or hand off to the unchanged web-page path.

    Raises `UrlFetchError` if `url` can't be reached at all.
    """
    for method in ("HEAD", "GET"):
        request = Request(url, headers={"User-Agent": _USER_AGENT}, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.headers.get("Content-Type"), response.geturl()
        except URLError as exc:
            if method == "GET":
                raise UrlFetchError(f"could not fetch {url!r}: {exc}") from exc
            continue  # HEAD rejected/failed — retry once with GET.
    raise UrlFetchError(f"could not fetch {url!r}")


def download_url_file(url: str, *, max_bytes: int, timeout: float) -> bytes:
    """Stream `url`'s body into memory, aborting with `UrlFetchTooLargeError`
    as soon as `max_bytes` is exceeded (docs/ingestion.md URL_FETCH_MAX_BYTES)
    rather than after downloading the whole thing.

    Raises `UrlFetchError` if `url` can't be reached at all.
    """
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise UrlFetchTooLargeError(
                        f"file at {url!r} exceeds URL_FETCH_MAX_BYTES ({max_bytes} bytes)"
                    )
                chunks.append(chunk)
            return b"".join(chunks)
    except URLError as exc:
        raise UrlFetchError(f"could not fetch {url!r}: {exc}") from exc


def derive_filename(url: str, kind: UploadKind) -> str:
    """A reasonable on-disk filename for a downloaded `url` of the given
    `kind` — reuses the URL's own filename when its extension already
    matches `kind` (so a human-readable name survives), otherwise builds one
    from the URL with the canonical extension for `kind` so the shared
    upload-processing path's `detect_upload_kind` recognizes it."""
    path_name = Path(urlparse(url).path).name
    if path_name:
        try:
            if detect_upload_kind(path_name) == kind:
                return path_name
        except UnsupportedUploadError:
            pass
        stem = Path(path_name).stem or "download"
    else:
        stem = urlparse(url).hostname or "download"
    return f"{stem}{_CANONICAL_EXTENSION[kind]}"
