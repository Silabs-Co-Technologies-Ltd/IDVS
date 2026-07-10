# IDVS

A minimal ID card verification upload system.

## Where to upload ID card images

Start the server and open the upload page:

```bash
python -m idvs.server
```

Then go to:

```text
http://127.0.0.1:8000/
```

Use the **Front of ID card** field for the front image and the **Back of ID card** field for the back image. The system accepts JPEG, PNG, and WebP files.

## Where uploaded files are stored

By default, uploads are saved in:

```text
data/id-cards/<submission-id>/
```

Each submission directory contains the front image, the back image, and `metadata.json`.

To store uploads somewhere else, set `IDVS_UPLOAD_DIR` before starting the server:

```bash
IDVS_UPLOAD_DIR=/secure/id-card-uploads python -m idvs.server
```

## Configuration

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `IDVS_HOST` | `127.0.0.1` | Bind address for the upload server. |
| `IDVS_PORT` | `8000` | Port for the upload server. |
| `IDVS_UPLOAD_DIR` | `data/id-cards` | Directory where uploaded ID card images are saved. |
| `IDVS_MAX_UPLOAD_BYTES` | `12582912` | Maximum total multipart request size. |

## Run tests

```bash
python -m pytest
```
