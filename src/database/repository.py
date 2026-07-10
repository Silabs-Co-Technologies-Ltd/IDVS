"""SQLite repository layer for students, KBI, admins, settings, and logs."""
from __future__ import annotations

import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from src.models.entities import KBIQuestion, Student, VerificationResult
from src.security.passwords import hash_secret

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS students (
  student_id INTEGER PRIMARY KEY AUTOINCREMENT,
  matric_number TEXT NOT NULL UNIQUE,
  surname TEXT NOT NULL,
  first_name TEXT NOT NULL,
  middle_name TEXT DEFAULT '',
  department TEXT NOT NULL,
  faculty TEXT NOT NULL,
  programme TEXT DEFAULT '',
  level TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  photo_path TEXT DEFAULT '',
  date_created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  date_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS kbi_questions (
  question_id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
  question TEXT NOT NULL,
  answer_hash TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  date_created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS admin_users (
  username TEXT PRIMARY KEY,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'admin',
  last_login TEXT
);
CREATE TABLE IF NOT EXISTS verification_logs (
  log_id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER,
  time TEXT NOT NULL,
  date TEXT NOT NULL,
  ocr_confidence REAL NOT NULL,
  verification_result TEXT NOT NULL,
  reason TEXT NOT NULL,
  captured_image_path TEXT,
  camera_used TEXT,
  processing_time REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_logs (
  audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT,
  action TEXT NOT NULL,
  details TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    """Small parameterized SQLite data-access facade."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            count = conn.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0]
            if count == 0:
                conn.execute(
                    "INSERT INTO admin_users(username, password_hash, role) VALUES (?, ?, ?)",
                    ("admin", hash_secret("admin123"), "super_admin"),
                )

    def add_student(self, student: Student) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO students(matric_number, surname, first_name, middle_name, department, faculty,
                programme, level, status, photo_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student.matric_number, student.surname, student.first_name, student.middle_name, student.department,
                 student.faculty, student.programme, student.level, student.status, student.photo_path),
            )
            return int(cur.lastrowid)

    def update_student(self, student: Student) -> None:
        if student.student_id is None:
            raise ValueError("student_id is required for updates")
        with self.connect() as conn:
            conn.execute(
                """UPDATE students SET matric_number=?, surname=?, first_name=?, middle_name=?, department=?, faculty=?,
                programme=?, level=?, status=?, photo_path=?, date_updated=CURRENT_TIMESTAMP WHERE student_id=?""",
                (student.matric_number, student.surname, student.first_name, student.middle_name, student.department,
                 student.faculty, student.programme, student.level, student.status, student.photo_path, student.student_id),
            )

    def delete_student(self, student_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM students WHERE student_id=?", (student_id,))

    def find_student_by_matric(self, matric_number: str) -> Student | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM students WHERE matric_number=?", (matric_number.strip(),)).fetchone()
        return self._student(row) if row else None

    def search_students(self, query: str) -> list[Student]:
        term = f"%{query.strip()}%"
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM students WHERE matric_number LIKE ? OR surname LIKE ? OR first_name LIKE ? ORDER BY surname", (term, term, term)).fetchall()
        return [self._student(r) for r in rows]

    def add_kbi_question(self, student_id: int, question: str, answer: str) -> int:
        with self.connect() as conn:
            cur = conn.execute("INSERT INTO kbi_questions(student_id, question, answer_hash) VALUES (?, ?, ?)", (student_id, question, hash_secret(answer)))
            return int(cur.lastrowid)

    def active_kbi_questions(self, student_id: int) -> list[KBIQuestion]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM kbi_questions WHERE student_id=? AND active=1", (student_id,)).fetchall()
        return [KBIQuestion(r["question_id"], r["student_id"], r["question"], r["answer_hash"], bool(r["active"])) for r in rows]

    def log_verification(self, result: VerificationResult, image_path: str = "", camera: str = "") -> None:
        now = datetime.now()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO verification_logs(student_id, time, date, ocr_confidence, verification_result, reason,
                captured_image_path, camera_used, processing_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (result.student.student_id if result.student else None, now.strftime("%H:%M:%S"), now.date().isoformat(),
                 result.confidence, "granted" if result.success else "denied", result.reason, image_path, camera, result.processing_time),
            )

    def import_students_csv(self, path: Path) -> int:
        count = 0
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self.add_student(Student(None, row["matric_number"], row["surname"], row["first_name"], row.get("middle_name", ""), row["department"], row["faculty"], row.get("programme", ""), row.get("level", "")))
                count += 1
        return count

    def backup(self, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        target = destination_dir / f"naub_idvs_backup_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"
        shutil.copy2(self.path, target)
        return target

    @staticmethod
    def _student(row: sqlite3.Row) -> Student:
        return Student(row["student_id"], row["matric_number"], row["surname"], row["first_name"], row["middle_name"], row["department"], row["faculty"], row["programme"], row["level"], row["status"], row["photo_path"])
