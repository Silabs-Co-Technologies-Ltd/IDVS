"""Configuration loader for the offline NAUB IDVS kiosk."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class AppSettings:
    database_path: Path = ROOT / "data" / "naub_idvs.sqlite3"
    ocr_confidence_threshold: float = 0.55
    matching_threshold: int = 80
    camera_index: int = 0
    voice_enabled: bool = False
    fullscreen_enabled: bool = True
    theme: str = "dark"
    backup_location: Path = ROOT / "data" / "backups"
    log_retention_days: int = 90
    session_timeout_minutes: int = 10
    roi_template: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)


def load_settings(path: Path | None = None) -> AppSettings:
    """Load JSON settings and coerce filesystem fields to absolute paths."""
    config_path = path or ROOT / "src" / "config" / "defaults.json"
    data: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ("database_path", "backup_location"):
        data[key] = Path(data[key])
        if not data[key].is_absolute():
            data[key] = ROOT / data[key]
    if "roi_template" in data:
        data["roi_template"] = {k: tuple(v) for k, v in data["roi_template"].items()}
    return AppSettings(**data)
