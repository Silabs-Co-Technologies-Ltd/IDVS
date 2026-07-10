"""Business-only verification and KBI engines."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    from difflib import SequenceMatcher

    class fuzz:  # type: ignore[no-redef]
        @staticmethod
        def token_set_ratio(left: str, right: str) -> float:
            l_tokens = set(left.upper().split())
            r_tokens = set(right.upper().split())
            if l_tokens and r_tokens and (l_tokens <= r_tokens or r_tokens <= l_tokens):
                return 100.0
            return SequenceMatcher(None, " ".join(sorted(l_tokens)), " ".join(sorted(r_tokens))).ratio() * 100

from src.config.settings import AppSettings
from src.database.repository import Database
from src.models.entities import KBIQuestion, OCRResult, Student, VerificationResult
from src.security.passwords import verify_secret


@dataclass(slots=True)
class PendingVerification:
    student: Student
    question: KBIQuestion
    ocr: OCRResult
    matched_fields: dict[str, float]


class VerificationEngine:
    """Coordinates OCR validation, database lookup, fuzzy matching, status, and KBI."""

    def __init__(self, db: Database, settings: AppSettings) -> None:
        self.db = db
        self.settings = settings

    def begin(self, ocr: OCRResult) -> PendingVerification | VerificationResult:
        start = time.perf_counter()
        if ocr.confidence < self.settings.ocr_confidence_threshold:
            return VerificationResult(False, "OCR confidence is below the configured threshold", None, ocr.confidence, {}, time.perf_counter() - start)
        student = self.db.find_student_by_matric(ocr.text("matric_number"))
        if student is None:
            return VerificationResult(False, "Matric number was not found in the student database", None, ocr.confidence, {}, time.perf_counter() - start)
        matches = {
            "name": float(fuzz.token_set_ratio(ocr.text("name"), student.full_name.upper())),
            "department": float(fuzz.token_set_ratio(ocr.text("department"), student.department.upper())),
            "faculty": float(fuzz.token_set_ratio(ocr.text("faculty"), student.faculty.upper())),
        }
        if min(matches.values()) < self.settings.matching_threshold:
            return VerificationResult(False, "OCR details do not sufficiently match database records", student, ocr.confidence, matches, time.perf_counter() - start)
        if student.status.lower() != "active":
            return VerificationResult(False, "Student record is inactive", student, ocr.confidence, matches, time.perf_counter() - start)
        questions = self.db.active_kbi_questions(student.student_id or 0)
        if not questions:
            return VerificationResult(False, "No active KBI question is configured for this student", student, ocr.confidence, matches, time.perf_counter() - start)
        return PendingVerification(student, random.choice(questions), ocr, matches)

    def complete_kbi(self, pending: PendingVerification, answer: str) -> VerificationResult:
        ok = verify_secret(answer, pending.question.answer_hash)
        return VerificationResult(ok, "KBI answer verified" if ok else "Incorrect KBI answer", pending.student, pending.ocr.confidence, pending.matched_fields, pending.ocr.processing_time)
