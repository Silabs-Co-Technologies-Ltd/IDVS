# Project Status

## Overview

The Automated Student ID Card Verification System (IDVS) is a Python-based verification project for Nigerian Army University Biu (NAUB) student ID cards. The repository currently contains two execution paths:

1. **Offline desktop kiosk**: the primary production-oriented Tkinter application launched from `main.py`.
2. **Lightweight web/serverless kiosk**: a standard-library WSGI interface for browser-based upload/camera testing, exposed through `idvs.wsgi` and `api/index.py`.

The application is designed to verify an ID card by extracting card text with OCR, matching the extracted matric number and student details against a local SQLite database, and then requiring Knowledge-Based Identification (KBI) before access is granted.

## Current Implementation Status

### Completed / Present

- **Application entrypoint**: `main.py` loads settings, configures logging, initializes the SQLite database, and launches the Tkinter kiosk.
- **Configuration system**: `src/config/settings.py` loads JSON defaults, resolves filesystem paths, and exposes runtime settings such as OCR threshold, fuzzy-match threshold, camera index, fullscreen mode, backup location, log retention, session timeout, and ROI templates.
- **Database layer**: `src/database/repository.py` initializes and manages SQLite tables for students, KBI questions, administrator users, verification logs, system settings, and audit logs.
- **Default administrator bootstrap**: the database creates a demonstration administrator user (`admin` / `admin123`) when no admin users exist.
- **Student management primitives**: repository methods support adding, updating, deleting, searching, CSV importing, and backing up student records.
- **KBI support**: KBI questions are stored with hashed answers, and active questions can be retrieved for verification.
- **Security helpers**: `src/security` provides password/KBI answer hashing and admin authentication.
- **OCR pipeline**: `src/ocr/pipeline.py` supports image loading, webcam capture, card contour detection, perspective correction, preprocessing, ROI extraction, EasyOCR field reading, confidence averaging, and text normalization.
- **Verification engine**: `src/verification/engine.py` performs confidence checks, matric-number database lookup, fuzzy matching of name/department/faculty, active-status validation, and KBI completion.
- **Offline kiosk UI**: `src/app/kiosk.py` contains the desktop kiosk interface.
- **Admin services**: `src/admin/services.py` exposes administrator workflows separately from the GUI layer.
- **Browser/serverless testing UI**: `idvs/server.py` and `idvs/wsgi.py` provide a browser kiosk, camera capture, `/verify` JSON endpoint, multipart `/upload` endpoint, and Vercel-compatible WSGI routing.
- **Upload safety checks**: web uploads require both front and back images, allow only JPEG/PNG/WebP content types, sanitize filenames, and write metadata for each submission.
- **Test coverage**: tests cover password hashing, database/KBI round trips, verification decisions, OCR text cleaning, admin login, OCR preprocessing, multipart parsing, upload persistence, WSGI form serving, browser verify endpoint behavior, and data URL decoding.

## Test Status

The project includes a pytest suite under `tests/`. At the time this status document was created, the test suite passes locally with:

```bash
python -m pytest
```

Current passing coverage focuses on core business logic, repository behavior, security helpers, upload parsing, and WSGI behavior. Tests that require optional OCR dependencies such as OpenCV/NumPy are written to skip gracefully when those packages are unavailable.

## Deployment / Runtime Status

### Offline Desktop Kiosk

The offline kiosk is the intended production mode. It requires dependencies from `requirements-offline.txt`, including OCR and image-processing packages such as EasyOCR, OpenCV, NumPy, Pillow, RapidFuzz, bcrypt, pyttsx3, and pytest.

Run locally with:

```bash
python -m pip install -r requirements-offline.txt
python main.py
```

### Optional Web / Vercel Testing Mode

The web path is intended for lightweight testing and does not install the full offline OCR dependency stack through `requirements.txt`. The WSGI app is exposed at `/` and includes `/upload` and `/verify` endpoints.

Run locally with:

```bash
python -m wsgiref.simple_server 8000 idvs.wsgi:app
```

Uploaded images are stored under `data/id-cards/` locally, or `/tmp/idvs-upload` on Vercel unless `IDVS_UPLOAD_DIR` is configured.

## Known Gaps / Risks

- **Default admin credentials must be changed before real deployment**. The demo account is useful for development but unsafe for production.
- **ROI templates need real card calibration**. OCR accuracy depends on configured regions of interest matching the actual NAUB ID-card layout.
- **Production data is not included**. Student records, KBI questions, and card images must be imported/configured for a real deployment.
- **Serverless storage is ephemeral**. Vercel uploads are suitable only for testing unless backed by durable external storage.
- **Browser `/verify` currently bypasses interactive KBI**. In serverless/browser verification, an OCR/database match that reaches the KBI stage is treated as a successful text match for quick kiosk feedback; the full offline engine still supports KBI completion.
- **Operational hardening remains necessary**. Before production use, review audit reporting, administrator workflows, backup restore procedures, logging retention enforcement, kiosk lock-down behavior, and device/camera calibration.
- **Dependency footprint is significant for offline OCR**. EasyOCR/OpenCV deployments should be packaged and tested for the target offline environment.

## Recommended Next Steps

1. Replace the default administrator password during first-run setup or migration.
2. Calibrate and validate ROI templates against real NAUB ID-card samples.
3. Import verified student records and KBI questions from an authoritative source.
4. Add end-to-end tests using representative card images and mocked OCR outputs.
5. Document production installation, offline wheel packaging, backup/restore, and operator procedures.
6. Decide whether the browser/serverless path should support full KBI interaction or remain a lightweight upload/testing utility.
7. Add deployment checks for database backups, audit-log review, and log retention.

## Overall Status

The project is in a functional prototype / pre-production state. Core verification logic, persistence, OCR integration points, security hashing, test coverage, and both desktop and browser-facing entrypoints are present. The main work remaining is operational: calibrating OCR for real ID cards, loading production data, hardening administrator and audit workflows, and preparing reliable offline deployment packages.
