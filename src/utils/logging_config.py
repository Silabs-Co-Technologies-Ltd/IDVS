"""Central logging configuration with separate operational log files."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_dir: Path = Path("logs")) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for name, filename in {
        "idvs": "application.log",
        "idvs.errors": "errors.log",
        "idvs.verification": "verification.log",
        "idvs.security": "security.log",
    }.items():
        logger = logging.getLogger(name)
        handler = RotatingFileHandler(log_dir / filename, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
