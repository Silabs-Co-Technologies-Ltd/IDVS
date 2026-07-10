from pathlib import Path

import pytest

from idvs.server import UploadError, parse_multipart, save_submission


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
