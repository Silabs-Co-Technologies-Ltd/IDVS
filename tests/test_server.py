from pathlib import Path

import pytest

from idvs.server import UploadedPart, UploadError, parse_multipart, save_submission


def multipart_body(boundary: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="front_image"; filename="front.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode() + b"front-bytes" + (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="back_image"; filename="back.jpg"\r\n'
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode() + b"back-bytes" + f"\r\n--{boundary}--\r\n".encode()


def test_parse_multipart_extracts_id_card_images():
    boundary = "test-boundary"

    parts = parse_multipart(f"multipart/form-data; boundary={boundary}", multipart_body(boundary))

    assert [part.field_name for part in parts] == ["front_image", "back_image"]
    assert parts[0].filename == "front.png"
    assert parts[0].content_type == "image/png"
    assert parts[0].body == b"front-bytes"


def test_save_submission_writes_front_back_and_metadata(tmp_path: Path):
    boundary = "test-boundary"
    parts = parse_multipart(f"multipart/form-data; boundary={boundary}", multipart_body(boundary))

    submission_id, saved = save_submission(parts, tmp_path)

    submission_dir = tmp_path / submission_id
    assert submission_dir.is_dir()
    assert sorted(path.name for path in saved) == ["back-back.jpg", "front-front.png"]
    assert (submission_dir / "metadata.json").exists()


def test_save_submission_requires_both_sides(tmp_path: Path):
    boundary = "only-front"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="front_image"; filename="front.png"\r\n'
        "Content-Type: image/png\r\n\r\nfront\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    parts = parse_multipart(f"multipart/form-data; boundary={boundary}", body)

    with pytest.raises(UploadError, match="front and back"):
        save_submission(parts, tmp_path)


def test_parse_multipart_preserves_binary_payload_edges():
    boundary = "binary-boundary"
    payload = b"\r\nPNG-bytes-that-end-with-crlf\r\n"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="front_image"; filename="front.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()

    parts = parse_multipart(f"multipart/form-data; boundary={boundary}", body)

    assert parts[0].body == payload


def test_save_submission_accepts_content_type_parameters(tmp_path: Path):
    parts = [
        UploadedPart("front_image", "front.png", "image/png; charset=binary", b"front"),
        UploadedPart("back_image", "back.jpeg", "image/jpeg", b"back"),
    ]

    _submission_id, saved = save_submission(parts, tmp_path)

    assert sorted(path.name for path in saved) == ["back-back.jpg", "front-front.png"]


def call_wsgi_app(path: str = "/", method: str = "GET", body: bytes = b"", content_type: str = ""):
    from io import BytesIO

    from idvs.wsgi import app

    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": content_type,
        "wsgi.input": BytesIO(body),
    }
    response_body = b"".join(app(environ, start_response))
    return captured["status"], dict(captured["headers"]), response_body


def test_wsgi_app_serves_upload_form():
    status, headers, body = call_wsgi_app()

    assert status.startswith("200")
    assert headers["Content-Type"] == "text/html; charset=utf-8"
    assert b"ID Card Verification Upload" in body


def test_wsgi_app_accepts_uploads_with_configured_directory(tmp_path: Path, monkeypatch):
    boundary = "wsgi-boundary"
    monkeypatch.setenv("IDVS_UPLOAD_DIR", str(tmp_path))

    status, _headers, body = call_wsgi_app(
        "/upload",
        "POST",
        multipart_body(boundary),
        f"multipart/form-data; boundary={boundary}",
    )

    assert status.startswith("200")
    assert b"Upload complete" in body
    assert len(list(tmp_path.iterdir())) == 1
