# Deployment Guide

## 1. Local development (SQLite, no Docker)

Requires Python 3.12+ (tested on 3.13.17) and ffmpeg (strongly recommended,
A-CV-10).

```bash
python -m pip install -r backend/requirements-dev.txt
```

```bash
python -m pytest
```

```bash
uvicorn backend.app:app --reload
```

The API runs at http://127.0.0.1:8000 (docs at `/docs`). Data goes to
`./storage/` (SQLite database, uploads, results), which is gitignored.

## 2. Docker Compose (PostgreSQL)

```bash
cp .env.example .env
```

Edit `.env` and set at least `POSTGRES_PASSWORD`. Set `FLAME_API_KEY` to
protect write operations.

```bash
docker compose up --build
```

* `api` on port 8000 runs as non-root uid 10001 and has a container health
  check on `/api/health`.
* `db` is PostgreSQL 16 with a health check, a named volume `pgdata`, and the
  password from `.env` only.
* Uploads and results live in the named volume `storage`.
* NASA image sequences are mounted read-only from `./data/raw`. They are not in
  the image. Download them with `backend/data/psi_client.py` (see
  `data/presets/samples.json` → `download_hint`).

**Verified on 2026-10-30** in the build environment, using equivalent
`docker run` commands with a Postgres 16 container:
* image build (1.5 GB);
* health status `healthy`;
* API key enforced (401 without it);
* synthetic analysis job completed with rows in PostgreSQL;
* NASA sample `PSI-23/19254C1` analysed inside the container: 159 limb fits,
  identical to the local run;
* zero error log lines.

`docker compose up` itself was not run in that environment.

### Builds behind restricted networks

* **Docker Hub rate limits (HTTP 429):**
  `docker build --build-arg BASE_IMAGE=mirror.gcr.io/library/python:3.13-slim .`
* **TLS-intercepting proxy:** place the proxy CA as `docker/extra-ca/<name>.crt`
  (gitignored). The Dockerfile installs it before `apt` (switched to HTTPS) and
  `pip` run. Pass the proxy with `--build-arg HTTPS_PROXY=...` and, if needed,
  `--network host`.

## 3. Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `FLAME_DATABASE_URL` | `sqlite:///./storage/flame.db` | SQLAlchemy URL; `postgresql+psycopg://user:pw@host:5432/db` for PostgreSQL |
| `FLAME_STORAGE_DIR` | `./storage` | Uploads and results |
| `FLAME_DATA_DIR` / `FLAME_MODELS_DIR` | `./data` / `./models` | Datasets, presets, model artifacts |
| `FLAME_API_KEY` | unset | When set, required for writes (`X-API-Key`) |
| `FLAME_CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins |
| `FLAME_MAX_UPLOAD_MB` | 500 | Upload size limit |
| `FLAME_MAX_WORKERS` | 2 | Concurrent analysis jobs |
| `FLAME_RATE_LIMIT_PER_MINUTE` | 30 | Per-client limit on expensive endpoints (0 disables) |
| `FLAME_TELEMETRY_BUFFER` | 2000 | Telemetry events kept per job for streaming |
| `FLAME_LOG_LEVEL` | INFO | JSON logs on stdout |

## 4. Operational notes

* **Jobs:** they run in an in-process thread pool. On restart, jobs that were
  `processing` become `failed` with an explanatory error (partial analyses
  cannot be resumed exactly), and `queued` jobs are resubmitted. The rate
  limiter and telemetry buffers are in-memory, so run **one API process**. Use
  a shared queue (e.g. Redis + RQ/Celery) before scaling horizontally.
* **Schema:** the schema is created with `create_all`, and a `schema_version`
  row (currently 1) is recorded. Any change to existing tables must bump
  `SCHEMA_VERSION` and ship a migration script. Alembic is the intended tool
  once the schema is no longer additive-only.
* **Security:**
  * uploads are checked by extension and file signature, streamed with a size
    cap, and stored under random names;
  * client file names never build paths;
  * responses contain no filesystem paths;
  * secrets come only from the environment;
  * the API key is compared in constant time.
* **Backups:** back up the `pgdata` and `storage` volumes. Model artifacts and
  processed datasets are reproducible from the repository and NASA PSI via
  their manifests.
