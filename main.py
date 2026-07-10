"""Entry point for the offline NAUB ID verification kiosk."""
from __future__ import annotations

from src.app.kiosk import KioskApp
from src.config.settings import load_settings
from src.database.repository import Database
from src.utils.logging_config import configure_logging


def main() -> None:
    settings = load_settings()
    configure_logging()
    db = Database(settings.database_path)
    KioskApp(settings, db).mainloop()


if __name__ == "__main__":
    main()
