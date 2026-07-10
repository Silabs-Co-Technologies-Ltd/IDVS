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
python -m pip install -r requirements-offline.txt
python main.py
```


## Optional Online Testing on Vercel

The offline kiosk remains the production entrypoint. For quick browser-based testing on Vercel, this repository also includes a lightweight WSGI upload app exposed from `api/index.py`. Vercel detects the Python runtime and serves the form at `/`; uploads post to `/upload`.

The Vercel app is intentionally standard-library only. Keep `requirements.txt` empty or limited to tiny serverless-only dependencies so Vercel does not bundle the offline OCR stack. Install the full kiosk dependencies from `requirements-offline.txt` for local/offline operation instead.

Serverless filesystems are ephemeral, so uploaded images are stored in `/tmp/idvs-upload` on Vercel unless `IDVS_UPLOAD_DIR` is set. Use this only for test submissions, not durable production storage.

```bash
python -m wsgiref.simple_server 8000 idvs.wsgi:app
```

Then open <http://localhost:8000>.

## Test

```bash
python -m pytest
```

## Offline Dependencies

Install dependencies from local wheels or a prepared offline package directory in deployment environments. No cloud OCR or internet service is used by the application.
