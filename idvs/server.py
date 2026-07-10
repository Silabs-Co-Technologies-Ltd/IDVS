"""Minimal ID card verification upload server.

Run with:
    python -m idvs.server

Uploaded ID card images are stored under data/id-cards/<submission-id>/.
"""
from __future__ import annotations

import html
import json
import os
import posixpath
import re
import shutil
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_ROOT = Path(os.environ.get("IDVS_UPLOAD_DIR", ROOT / "data" / "id-cards"))
MAX_UPLOAD_BYTES = int(os.environ.get("IDVS_MAX_UPLOAD_BYTES", str(12 * 1024 * 1024)))
ALLOWED_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@dataclass(frozen=True)
class UploadedPart:
    field_name: str
    filename: str
    content_type: str
    body: bytes


class UploadError(ValueError):
    """Raised when an upload request is malformed or unsafe."""


def _safe_filename(filename: str, fallback: str) -> str:
    name = posixpath.basename(filename.replace("\\", "/")).strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return name or fallback


def parse_multipart(content_type: str, body: bytes) -> list[UploadedPart]:
    """Parse the small multipart/form-data subset needed for image uploads."""
    match = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', content_type)
    if not match:
        raise UploadError("Missing multipart boundary.")
    boundary = (match.group(1) or match.group(2)).encode()
    delimiter = b"--" + boundary
    parts: list[UploadedPart] = []

    for raw_part in body.split(delimiter):
        if raw_part in {b"", b"--", b"--\r\n"}:
            continue
        raw_part = raw_part.strip(b"\r\n")
        if raw_part == b"--":
            continue
        headers_blob, sep, payload = raw_part.partition(b"\r\n\r\n")
        if not sep:
            raise UploadError("Malformed multipart section.")
        headers: dict[str, str] = {}
        for line in headers_blob.decode("utf-8", "replace").split("\r\n"):
            key, _, value = line.partition(":")
            headers[key.lower()] = value.strip()

        disposition = headers.get("content-disposition", "")
        field = re.search(r'name="([^"]+)"', disposition)
        filename = re.search(r'filename="([^"]*)"', disposition)
        if not field or not filename or not filename.group(1):
            continue
        content_type_header = headers.get("content-type", "application/octet-stream").lower()
        parts.append(
            UploadedPart(
                field_name=field.group(1),
                filename=filename.group(1),
                content_type=content_type_header,
                body=payload,
            )
        )
    return parts


def save_submission(parts: Iterable[UploadedPart], upload_root: Path = UPLOAD_ROOT) -> tuple[str, list[Path]]:
    """Validate and persist front/back ID-card images."""
    selected = {part.field_name: part for part in parts if part.field_name in {"front_image", "back_image"}}
    missing = {"front_image", "back_image"} - set(selected)
    if missing:
        raise UploadError("Upload both the front and back images of the ID card.")

    submission_id = uuid.uuid4().hex
    submission_dir = upload_root / submission_id
    submission_dir.mkdir(parents=True, exist_ok=False)
    saved: list[Path] = []

    try:
        for field_name, label in (("front_image", "front"), ("back_image", "back")):
            part = selected[field_name]
            if part.content_type not in ALLOWED_CONTENT_TYPES:
                raise UploadError("Only JPEG, PNG, and WebP images are accepted.")
            if not part.body:
                raise UploadError("Uploaded image files must not be empty.")
            suffix = ALLOWED_CONTENT_TYPES[part.content_type]
            original = _safe_filename(part.filename, f"{label}{suffix}")
            destination = submission_dir / f"{label}-{original}"
            if destination.suffix.lower() not in ALLOWED_CONTENT_TYPES.values():
                destination = destination.with_suffix(suffix)
            destination.write_bytes(part.body)
            saved.append(destination)

        metadata = {
            "submission_id": submission_id,
            "upload_directory": str(submission_dir.relative_to(ROOT) if submission_dir.is_relative_to(ROOT) else submission_dir),
            "files": [path.name for path in saved],
        }
        (submission_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return submission_id, saved
    except Exception:
        shutil.rmtree(submission_dir, ignore_errors=True)
        raise


INDEX_HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>IDVS - ID Card Upload</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background: #f6f7fb; color: #172033; }
    main { max-width: 760px; margin: 48px auto; background: white; border-radius: 18px; padding: 32px; box-shadow: 0 18px 55px #1820331f; }
    h1 { margin-top: 0; }
    .hint { background: #eef5ff; border-left: 5px solid #2563eb; padding: 16px; border-radius: 10px; }
    label { display: block; font-weight: 700; margin-top: 22px; }
    input[type=file] { display: block; width: 100%; margin-top: 8px; padding: 14px; border: 1px dashed #94a3b8; border-radius: 12px; }
    button { margin-top: 26px; padding: 14px 22px; border: 0; border-radius: 999px; background: #0f172a; color: white; font-weight: 800; cursor: pointer; }
    code { background: #f1f5f9; padding: 2px 6px; border-radius: 6px; }
  </style>
</head>
<body><main>
  <h1>ID Card Verification Upload</h1>
  <p>Upload clear images of both sides of the ID card. Accepted formats: JPEG, PNG, or WebP.</p>
  <div class=\"hint\"><strong>Where to upload:</strong> use this page at <code>/</code>. Files are saved on the server in <code>data/id-cards/&lt;submission-id&gt;/</code>.</div>
  <form method=\"post\" action=\"/upload\" enctype=\"multipart/form-data\">
    <label for=\"front_image\">Front of ID card</label>
    <input id=\"front_image\" name=\"front_image\" type=\"file\" accept=\"image/jpeg,image/png,image/webp\" required>
    <label for=\"back_image\">Back of ID card</label>
    <input id=\"back_image\" name=\"back_image\" type=\"file\" accept=\"image/jpeg,image/png,image/webp\" required>
    <button type=\"submit\">Upload ID card images</button>
  </form>
</main></body></html>
"""


class IDVSHandler(BaseHTTPRequestHandler):
    server_version = "IDVS/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send_html(INDEX_HTML)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/upload":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            if length <= 0 or length > MAX_UPLOAD_BYTES:
                raise UploadError(f"Upload must be between 1 byte and {MAX_UPLOAD_BYTES} bytes.")
            parts = parse_multipart(self.headers.get("content-type", ""), self.rfile.read(length))
            submission_id, saved = save_submission(parts)
        except UploadError as exc:
            self._send_html(self._result_page("Upload problem", str(exc)), status=HTTPStatus.BAD_REQUEST)
            return
        self._send_html(
            self._result_page(
                "Upload complete",
                f"Saved {len(saved)} images to data/id-cards/{html.escape(submission_id)}/.",
            )
        )

    def _result_page(self, title: str, message: str) -> str:
        return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title></head>
<body><main><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p><p><a href=\"/\">Upload another ID card</a></p></main></body></html>"""

    def _send_html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    host = os.environ.get("IDVS_HOST", "127.0.0.1")
    port = int(os.environ.get("IDVS_PORT", "8000"))
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"IDVS upload server running at http://{host}:{port}")
    print(f"Upload storage: {UPLOAD_ROOT}")
    ThreadingHTTPServer((host, port), IDVSHandler).serve_forever()


if __name__ == "__main__":
    main()
