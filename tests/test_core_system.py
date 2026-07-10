from pathlib import Path

import pytest

from src.config.settings import AppSettings
from src.database.repository import Database
from src.models.entities import OCRField, OCRResult, Student, VerificationResult
from src.ocr.pipeline import OCRService
from src.security.auth import AuthService
from src.security.passwords import hash_secret, verify_secret
from src.verification.engine import PendingVerification, VerificationEngine


def settings(tmp_path: Path) -> AppSettings:
    return AppSettings(database_path=tmp_path / "idvs.sqlite3", roi_template={"matric_number": (0, 0, 1, 1)})


def test_password_hashes_are_not_plaintext_and_verify():
    hashed = hash_secret(" Maiduguri ")
    assert hashed != "Maiduguri"
    assert verify_secret("maiduguri", hashed)


def test_database_student_and_kbi_roundtrip(tmp_path):
    db = Database(tmp_path / "idvs.sqlite3")
    student_id = db.add_student(Student(None, "NAUB/CSC/001", "MUSA", "ALI", department="Computer Science", faculty="Computing"))
    db.add_kbi_question(student_id, "What is your home town?", "Biu")

    student = db.find_student_by_matric("NAUB/CSC/001")

    assert student is not None
    assert student.full_name == "MUSA ALI"
    assert len(db.active_kbi_questions(student_id)) == 1


def test_verification_requires_kbi_after_ocr_and_database_match(tmp_path):
    app_settings = settings(tmp_path)
    db = Database(app_settings.database_path)
    student_id = db.add_student(Student(None, "NAUB/CSC/001", "MUSA", "ALI", department="Computer Science", faculty="Computing"))
    db.add_kbi_question(student_id, "What is your home town?", "Biu")
    ocr = OCRResult({
        "matric_number": OCRField("matric_number", "NAUB/CSC/001", 0.95),
        "name": OCRField("name", "ALI MUSA", 0.91),
        "department": OCRField("department", "COMPUTER SCIENCE", 0.93),
        "faculty": OCRField("faculty", "COMPUTING", 0.90),
    }, 0.92)

    engine = VerificationEngine(db, app_settings)
    pending = engine.begin(ocr)

    assert isinstance(pending, PendingVerification)
    assert engine.complete_kbi(pending, "Biu").success
    assert not engine.complete_kbi(pending, "Lagos").success


def test_low_ocr_confidence_is_denied(tmp_path):
    app_settings = settings(tmp_path)
    db = Database(app_settings.database_path)
    result = VerificationEngine(db, app_settings).begin(OCRResult({}, 0.1))
    assert isinstance(result, VerificationResult)
    assert not result.success
    assert "confidence" in result.reason.lower()


def test_ocr_text_cleaning_normalizes_matric_number():
    assert OCRService.clean_text("matric_number", " naub / csc - 001! ") == "NAUB/CSC-001"


def test_admin_authentication(tmp_path):
    db = Database(tmp_path / "idvs.sqlite3")
    auth = AuthService(db)
    assert auth.login("admin", "admin123")
    assert not auth.login("admin", "wrong")


def test_ocr_preprocess_accepts_grayscale_images(tmp_path):
    from src.ocr.pipeline import cv2, np

    if cv2 is None or np is None:
        pytest.skip("OpenCV and NumPy are not installed")
    app_settings = settings(tmp_path)
    image = np.full((64, 64), 127, dtype=np.uint8)

    processed = OCRService(app_settings).preprocess(image)

    assert processed.shape == image.shape
