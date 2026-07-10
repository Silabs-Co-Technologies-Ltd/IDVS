"""Administrative use cases kept outside the Tkinter interface."""
from __future__ import annotations

from pathlib import Path

from src.database.repository import Database
from src.models.entities import Student


class StudentAdminService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add_student(self, student: Student, kbi_pairs: list[tuple[str, str]] | None = None) -> int:
        student_id = self.db.add_student(student)
        for question, answer in kbi_pairs or []:
            self.db.add_kbi_question(student_id, question, answer)
        return student_id

    def deactivate(self, student_id: int) -> None:
        students = self.db.search_students("")
        student = next(s for s in students if s.student_id == student_id)
        student.status = "inactive"
        self.db.update_student(student)

    def import_csv(self, path: Path) -> int:
        return self.db.import_students_csv(path)
