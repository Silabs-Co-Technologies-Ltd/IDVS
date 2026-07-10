"""WSGI entrypoint for hosting the IDVS upload form on serverless platforms."""
from __future__ import annotations

import html
import os
from http import HTTPStatus
from pathlib import Path
from typing import Callable, Iterable

from idvs.server import INDEX_HTML, MAX_UPLOAD_BYTES, UploadError, parse_multipart, save_submission

StartResponse = Callable[[str, list[tuple[str, str]]], None]


def default_upload_root() -> Path:
    """Return a writable upload directory for local or serverless execution."""
    configured = os.environ.get("IDVS_UPLOAD_DIR")
    if configured:
        return Path(configured)
    if os.environ.get("VERCEL"):
        return Path("/tmp/idvs-upload")
    return Path(__file__).resolve().parents[1] / "data" / "id-cards"


def _html_response(start_response: StartResponse, content: str, status: HTTPStatus = HTTPStatus.OK) -> list[bytes]:
    payload = content.encode("utf-8")
    start_response(
        f"{status.value} {status.phrase}",
        [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(payload)))],
    )
    return [payload]


def _result_page(title: str, message: str) -> str:
    return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title></head>
<body><main><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p><p><a href=\"/\">Upload another ID card</a></p></main></body></html>"""


def app(environ: dict[str, object], start_response: StartResponse) -> Iterable[bytes]:
    """Serve the upload UI and multipart endpoint as a Vercel-compatible WSGI app."""
    method = str(environ.get("REQUEST_METHOD", "GET")).upper()
    path = str(environ.get("PATH_INFO", "/")) or "/"

    if path.startswith("/api"):
        # Vercel can invoke this file at /api/index directly during local testing.
        path = path.removeprefix("/api/index") or path.removeprefix("/api") or "/"

    if method == "GET" and path == "/":
        return _html_response(start_response, INDEX_HTML)

    if method == "POST" and path == "/upload":
        try:
            length = int(str(environ.get("CONTENT_LENGTH") or "0"))
            if length <= 0 or length > MAX_UPLOAD_BYTES:
                raise UploadError(f"Upload must be between 1 byte and {MAX_UPLOAD_BYTES} bytes.")
            body_stream = environ["wsgi.input"]
            body = body_stream.read(length)  # type: ignore[attr-defined]
            content_type = str(environ.get("CONTENT_TYPE", ""))
            upload_root = default_upload_root()
            upload_root.mkdir(parents=True, exist_ok=True)
            submission_id, saved = save_submission(parse_multipart(content_type, body), upload_root=upload_root)
        except UploadError as exc:
            return _html_response(start_response, _result_page("Upload problem", str(exc)), HTTPStatus.BAD_REQUEST)
        return _html_response(
            start_response,
            _result_page("Upload complete", f"Saved {len(saved)} images for submission {html.escape(submission_id)}."),
        )

    return _html_response(start_response, _result_page("Not found", "The requested page does not exist."), HTTPStatus.NOT_FOUND)
