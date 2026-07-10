# Automated Student ID Card Verification System for NAUB

A production-oriented, offline Python desktop kiosk for verifying Nigerian Army University Biu student ID cards. The system combines local image processing, EasyOCR field extraction, SQLite database checks, fuzzy matching, and Knowledge-Based Identification (KBI) so that possession of a stolen card is not sufficient for access.

## Architecture

- `main.py` starts the offline Tkinter kiosk.
- `src/config` loads configurable thresholds, camera index, fullscreen mode, backup location, and ID-card ROI templates.
- `src/database` owns SQLite schema creation, parameterized repositories, CSV import, backups, verification logs, admin users, settings, and audit tables.
- `src/models` contains dataclasses used across the application.
- `src/ocr` performs card detection, perspective correction, preprocessing, ROI extraction, and EasyOCR per field.
- `src/verification` contains business-only verification and KBI workflow logic.
- `src/security` hashes administrator passwords and KBI answers using bcrypt.
- `src/admin` exposes administrator use cases independently from the GUI.
- `src/app` contains the kiosk Tkinter interface.

## Default Administrator

The first database initialization creates a local administrator account for demonstration:

- Username: `admin`
- Password: `admin123`

Change it before real deployment.

## Run

```bash
python main.py
```

## Test

```bash
python -m pytest
```

## Offline Dependencies

Install dependencies from local wheels or a prepared offline package directory in deployment environments. No cloud OCR or internet service is used by the application.
