"""Minimal ID card verification upload server.

Run with:
    python -m idvs.server

Uploaded ID card images are stored under data/id-cards/<submission-id>/.
"""
from __future__ import annotations

import base64
import binascii
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
from typing import Any, Iterable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_ROOT = Path(os.environ.get("IDVS_UPLOAD_DIR", ROOT / "data" / "id-cards"))
MAX_UPLOAD_BYTES = int(os.environ.get("IDVS_MAX_UPLOAD_BYTES", str(12 * 1024 * 1024)))
ALLOWED_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
DATABASE_PATH = Path(os.environ.get("IDVS_DATABASE_PATH", ROOT / "data" / "naub_idvs.sqlite3"))


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
        if raw_part.startswith(b"\r\n"):
            raw_part = raw_part[2:]
        if raw_part.endswith(b"\r\n"):
            raw_part = raw_part[:-2]
        if raw_part.endswith(b"--"):
            raw_part = raw_part[:-2]
            if raw_part.endswith(b"\r\n"):
                raw_part = raw_part[:-2]
        if raw_part == b"":
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
        content_type_header = headers.get("content-type", "application/octet-stream").split(";", 1)[0].strip().lower()
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
            content_type = part.content_type.split(";", 1)[0].strip().lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise UploadError("Only JPEG, PNG, and WebP images are accepted.")
            if not part.body:
                raise UploadError("Uploaded image files must not be empty.")
            suffix = ALLOWED_CONTENT_TYPES[content_type]
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


KIOSK_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>ID Card Verification Upload - IDVS Kiosk</title>
  <style>
    :root { color-scheme: dark; --ok: #16a34a; --bad: #dc2626; --idle: #2563eb; }
    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; overflow: hidden; background: #020617; color: white; font-family: system-ui, sans-serif; }
    main { min-height: 100%; display: grid; grid-template-columns: 1fr 380px; gap: 24px; padding: 24px; }
    .camera { position: relative; border-radius: 28px; overflow: hidden; background: #0f172a; box-shadow: 0 24px 80px #0008; }
    video { width: 100%; height: 100%; object-fit: cover; transform: scaleX(-1); }
    .guide { position: absolute; inset: 16%; border: 6px solid #f8fafc; border-radius: 24px; box-shadow: 0 0 0 999px #0007; }
    aside { display: flex; flex-direction: column; gap: 18px; justify-content: center; }
    h1 { font-size: clamp(2rem, 4vw, 4.8rem); margin: 0; line-height: 1; }
    .status { padding: 28px; border-radius: 24px; background: var(--idle); min-height: 210px; display: grid; align-content: center; gap: 12px; }
    .status.ok { background: var(--ok); } .status.bad { background: var(--bad); }
    .label { font-size: 0.85rem; letter-spacing: 0.18em; opacity: 0.8; text-transform: uppercase; }
    .message { font-size: 1.35rem; font-weight: 800; }
    button { border: 0; border-radius: 999px; padding: 18px 24px; font-weight: 900; font-size: 1rem; color: #0f172a; cursor: pointer; }
    canvas { display: none; }
    @media (max-width: 900px) { main { grid-template-columns: 1fr; grid-template-rows: 1fr auto; } aside { justify-content: start; } }
  </style>
</head>
<body><main>
  <section class="camera"><video id="camera" autoplay muted playsinline></video><div class="guide" aria-hidden="true"></div></section>
  <aside>
    <h1>IDVS Kiosk</h1>
    <div id="status" class="status"><div class="label">Waiting for ID card</div><div id="message" class="message">Place the ID card inside the frame.</div><pre id="details"></pre></div>
    <button id="fullscreen">Open fullscreen kiosk mode</button>
    <button id="scan">Scan now</button>
  </aside>
  <canvas id="snapshot"></canvas>
<script>
const video = document.getElementById('camera');
const canvas = document.getElementById('snapshot');
const statusBox = document.getElementById('status');
const message = document.getElementById('message');
const details = document.getElementById('details');
let scanning = false;
function setStatus(kind, text, extra='') { statusBox.className = 'status ' + kind; message.textContent = text; details.textContent = extra; }
async function startCamera() {
  const stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment'}, audio: false});
  video.srcObject = stream;
}
async function verifyFrame() {
  if (scanning || video.readyState < 2) return;
  scanning = true; setStatus('', 'Scanning ID card...');
  canvas.width = video.videoWidth; canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  const image = canvas.toDataURL('image/jpeg', 0.9);
  try {
    const response = await fetch('/verify', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({image})});
    const result = await response.json();
    setStatus(result.success ? 'ok' : 'bad', result.success ? 'ACCESS GRANTED' : 'ACCESS DENIED', (result.reason || '') + '\nMatric: ' + (result.matric_number || 'not read'));
  } catch (error) { setStatus('bad', 'Verification failed', String(error)); }
  setTimeout(() => { scanning = false; setStatus('', 'Place the ID card inside the frame.'); }, 4500);
}
document.getElementById('fullscreen').onclick = () => document.documentElement.requestFullscreen?.();
document.getElementById('scan').onclick = verifyFrame;
startCamera().catch(err => setStatus('bad', 'Camera unavailable', String(err)));
setInterval(verifyFrame, 5000);
</script>
</main></body></html>
"""

INDEX_HTML = KIOSK_HTML



def _json_safe_student(student: Any) -> dict[str, Any] | None:
    if student is None:
        return None
    return {
        "student_id": student.student_id,
        "matric_number": student.matric_number,
        "name": student.full_name,
        "department": student.department,
        "faculty": student.faculty,
        "status": student.status,
    }


def verify_image_bytes(image_bytes: bytes, database_path: Path = DATABASE_PATH) -> dict[str, Any]:
    """Run OCR on a captured ID-card image and verify it against SQLite records."""
    from tempfile import NamedTemporaryFile

    from src.config.settings import load_settings
    from src.database.repository import Database
    from src.models.entities import VerificationResult
    from src.ocr.pipeline import OCRService
    from src.verification.engine import PendingVerification, VerificationEngine

    settings = load_settings()
    settings.database_path = database_path
    db = Database(settings.database_path)

    with NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = Path(tmp.name)
    try:
        ocr_service = OCRService(settings)
        ocr = ocr_service.run(ocr_service.load_image(tmp_path), tmp_path)
        step = VerificationEngine(db, settings).begin(ocr)
        if isinstance(step, PendingVerification):
            verified = VerificationResult(True, "ID card text matched an active SQLite student record", step.student, ocr.confidence, step.matched_fields, ocr.processing_time)
        else:
            verified = step
        db.log_verification(verified, str(tmp_path), "browser")
        return {
            "success": verified.success,
            "reason": verified.reason,
            "student": _json_safe_student(verified.student),
            "confidence": verified.confidence,
            "matched_fields": verified.matched_fields,
            "matric_number": ocr.text("matric_number"),
        }
    finally:
        tmp_path.unlink(missing_ok=True)


def decode_data_url(data_url: str) -> bytes:
    """Decode a browser canvas data URL into raw image bytes."""
    prefix, separator, payload = data_url.partition(",")
    if not separator or ";base64" not in prefix or not prefix.startswith("data:image/"):
        raise UploadError("Expected a base64 image data URL.")
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise UploadError("Image data could not be decoded.") from exc


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
        if path == "/verify":
            self._handle_verify()
            return
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

    def _handle_verify(self) -> None:
        try:
            length = int(self.headers.get("content-length", "0"))
            if length <= 0 or length > MAX_UPLOAD_BYTES:
                raise UploadError(f"Verification payload must be between 1 byte and {MAX_UPLOAD_BYTES} bytes.")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = verify_image_bytes(decode_data_url(str(payload.get("image", ""))))
        except (UploadError, json.JSONDecodeError) as exc:
            result = {"success": False, "reason": str(exc)}
        self._send_json(result)

    def _result_page(self, title: str, message: str) -> str:
        return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title></head>
<body><main><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p><p><a href=\"/\">Upload another ID card</a></p></main></body></html>"""

    def _send_json(self, content: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(content).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

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
