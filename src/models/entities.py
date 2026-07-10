"""Domain models shared by the GUI, database layer, and verification engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class Student:
    student_id: int | None
    matric_number: str
    surname: str
    first_name: str
    middle_name: str = ""
    department: str = ""
    faculty: str = ""
    programme: str = ""
    level: str = ""
    status: str = "active"
    photo_path: str = ""
    date_created: datetime | None = None
    date_updated: datetime | None = None

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.surname, self.first_name, self.middle_name) if p).strip()


@dataclass(slots=True)
class KBIQuestion:
    question_id: int | None
    student_id: int
    question: str
    answer_hash: str
    active: bool = True
    date_created: datetime | None = None


@dataclass(slots=True)
class OCRField:
    name: str
    text: str
    confidence: float
    bbox: list[tuple[int, int]] = field(default_factory=list)


@dataclass(slots=True)
class OCRResult:
    fields: dict[str, OCRField]
    confidence: float
    image_path: Path | None = None
    processing_time: float = 0.0

    def text(self, field_name: str) -> str:
        return self.fields.get(field_name, OCRField(field_name, "", 0.0)).text


@dataclass(slots=True)
class VerificationResult:
    success: bool
    reason: str
    student: Student | None
    confidence: float
    matched_fields: dict[str, float]
    processing_time: float
