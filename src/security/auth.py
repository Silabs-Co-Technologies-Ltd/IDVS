"""Administrator authentication service."""
from __future__ import annotations

from datetime import datetime

from src.database.repository import Database
from src.security.passwords import hash_secret, verify_secret


class AuthService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def login(self, username: str, password: str) -> bool:
        with self.db.connect() as conn:
            row = conn.execute("SELECT password_hash FROM admin_users WHERE username=?", (username.strip(),)).fetchone()
            if not row or not verify_secret(password, row["password_hash"]):
                return False
            conn.execute("UPDATE admin_users SET last_login=? WHERE username=?", (datetime.now().isoformat(timespec="seconds"), username.strip()))
            return True

    def create_admin(self, username: str, password: str, role: str = "admin") -> None:
        with self.db.connect() as conn:
            conn.execute("INSERT INTO admin_users(username, password_hash, role) VALUES (?, ?, ?)", (username.strip(), hash_secret(password), role))
