<p align="center">
  <img src="docs/images/hermes_logo_v3.png" alt="Hermes Logo" width="600"/>
</p>

<h1 align="center">⚡ Hermes</h1>

<p align="center">
  <em>A lightweight, pluggable async batch processing scheduler for CSV files and Generative AI pipelines.</em>
</p>

Hermes is an **independent background process** that watches a shared inbox folder, reads CSV files in memory-safe chunks, and dispatches work to a thread pool of AI workers — completely decoupled from any Web App upstream.

```
./uploads_web  ──►  Hermes  ──►  ThreadPoolExecutor  ──►  Generative AI API
  (inbox)           (loop)         (N workers)              (streaming)
```

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Extending Hermes — Custom Workers](#extending-hermes--custom-workers)
- [Processing Loop](#processing-loop)
- [Logging](#logging)
- [GUI Control Room & Multi-Pool Management](#gui-control-room--multi-pool-management)
- [Testing](#testing)
- [Roadmap](#roadmap)

---

## Architecture

Hermes is **Process 2** in a two-process system. It shares no memory, no imports, and no state with the Web App. The only communication channel between the two is the **shared file system** and the PostgreSQL database.

![Architecture](./docs/images/Code_Generated_Image.png)

---

## Project Structure

```
Hermes/
├── alembic.ini                    # Alembic entry configuration
├── docker-compose.yml             # Local app and PostgreSQL services
├── Dockerfile                     # Reproducible runtime image
├── pyproject.toml                 # Dependency and tool configuration
├── uv.lock                        # Reproducible uv resolution
├── requirements-runtime.txt       # Minimal Docker runtime dependencies
├── requirements.txt               # Export including optional extras
├── docs/images/                   # Images referenced by this README
├── scripts/
│   ├── create_admin.py            # Create a local Control Room account
│   └── smoke_upload.py            # Manual CSV upload smoke client
├── src/
│   ├── main.py                    # Processing-engine entry point
│   ├── api/                       # Engine health endpoint
│   ├── core/                      # Configuration and filesystem pipeline
│   ├── db/
│   │   ├── migrations/            # Canonical Alembic history
│   │   ├── db.py                  # Engine and session factory
│   │   ├── models.py              # SQLAlchemy models
│   │   ├── repository.py          # Database operations
│   │   └── status.py              # Canonical states and transitions
│   ├── gui/
│   │   ├── pages/                 # Control Room HTML
│   │   ├── routes/                # Control Room FastAPI routes
│   │   └── static/                # Control Room CSS, JS and images
│   └── workers/                   # Pools and LLM workers
└── test/                          # Automated pytest suite
```

The Control Room under `src/gui` is an internal technical interface. It is
separate from the user-facing React application maintained in
`hermes-webapp`.

### Dependency files

`pyproject.toml` is the source of truth for Python dependencies and optional
capabilities. `uv.lock` pins the complete resolution used by local development.
`requirements-runtime.txt` contains the smaller runtime installed in the Docker
image, while `requirements.txt` is generated with:

```bash
uv export --all-extras --no-hashes --output-file requirements.txt
```

When dependencies change, update `pyproject.toml`, regenerate `uv.lock` and the
export, and review `requirements-runtime.txt` if the Docker runtime is affected.

---

## Getting Started

### Prerequisites

- Docker and Docker Compose (Recommended)
- Python 3.12+ (if running locally without Docker)
- pip or uv

### Running with Docker (Recommended)

Hermes now supports full containerization with Docker and Docker Compose. This will spin up the Hermes engine/GUI and a PostgreSQL database automatically.

```bash
git clone --branch develop https://github.com/Ilpupi00/Hermes.git
cd hermes
cp .env.example .env
# Replace every change-me value in .env
docker compose up -d --build
```

This command will automatically:

- Start a `postgres:16-alpine` database.
- Wait for PostgreSQL to be ready before starting Hermes.
- Run `alembic upgrade head` before starting the Control Room.
- Build and start the `hermes_app` container, mounting the local
  `uploads_web`, `processed`, `failed`, and `interrupted` folders.
- Expose the Control Room dashboard on port `8000`.

You can access the Control Room dashboard at [http://localhost:8000](http://localhost:8000).
Readiness can be checked at
[http://localhost:8000/health](http://localhost:8000/health); it returns HTTP
200 only when both the web application and PostgreSQL are reachable.

For a manual upload smoke test against an already running Control Room:

```bash
uv run python scripts/smoke_upload.py path/to/input.csv --model-id 1
```

The script does not embed credentials. Configure any required Hugging Face
token in the local `.env` before starting Hermes.

On a new database, create the first Control Room administrator from a terminal:

```bash
docker exec -it hermes_app python scripts/create_admin.py <username>
```

Replace `<username>` with the desired login name. The script asks for the
password and confirmation without displaying or storing them in shell history.
Use at least eight characters. Each local installation has its own
administrator account.

Schema upgrades are versioned with Alembic and are applied automatically at
container startup. To inspect or apply them manually:

```bash
docker compose exec hermes alembic current
docker compose exec hermes alembic upgrade head
```

`docker compose down -v` is required only for an intentionally destructive,
clean database reset; it is not the normal upgrade procedure.

### Local Installation (Without Docker)

Using `uv` (Recommended):

```bash
git clone --branch develop https://github.com/Ilpupi00/Hermes.git
cd hermes
uv sync
```

Install only the optional capabilities that are needed:

```bash
uv sync --extra dev         # test and coverage tools
uv sync --extra desktop     # native PyWebView window
uv sync --extra local-llm   # PyTorch/Transformers inference on the host
```

On Apple Silicon, native `local-llm` inference must run on macOS to use MPS.
The Docker image intentionally excludes PyTorch and Transformers because its
Linux environment cannot use the Mac GPU. Docker still supports Hugging Face
remote inference and OpenAI-compatible servers such as Ollama.

Using standard `pip`:

```bash
git clone --branch develop https://github.com/Ilpupi00/Hermes.git
cd hermes
uv venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### Setup

```bash
cp .env.example .env
# Sostituisci tutti i valori change-me e inserisci gli eventuali token
```

Genera una chiave JWT distinta per questo ambiente:

```bash
openssl rand -hex 32
```

Inserisci il risultato in `SECRET_KEY` dentro `.env`. Il file `.env` è
ignorato da Git: non commetterlo e non condividere token, password o chiavi
negli screenshot.

Create the required folders (Hermes will also create them on startup if missing):

```bash
mkdir -p uploads_web processed failed interrupted
```

These are runtime directories and are intentionally ignored by Git:

| Directory | Current role |
| --- | --- |
| `uploads_web` | Shared inbox watched for new CSV files |
| `processed` | Current working/archive area; it will be split in a later phase |
| `failed` | Files whose processing failed |
| `interrupted` | Files deferred during shutdown or interruption |

Do not place source files or permanent documentation in these directories.

Apply pending database migrations:

```bash
uv run alembic upgrade head
```

### Run

Using `uv` (Recommended):

```bash
uv run python -m src.main
```

Using python directly:

```bash
python -m src.main
```

### Run GUI Control Room Locally

To start the GUI Control Room (FastAPI + PyWebView):

Using `uv` (Recommended):

```bash
uv run python -m src.gui.app
```

Using python directly:

```bash
python -m src.gui.app
```

---

## Configuration

All settings are loaded from environment variables or a `.env` file in the project root.

| Variable                      | Default / requirement | Description                                        |
| ----------------------------- | --------------------- | -------------------------------------------------- |
| `DB_HOST`                     | `localhost`           | PostgreSQL host (`db` in Docker Compose)            |
| `DB_PORT`                     | `5432`                | PostgreSQL port                                     |
| `DB_NAME`                     | `postgres`            | PostgreSQL database                                 |
| `DB_USER`                     | `postgres`            | PostgreSQL user                                     |
| `DB_PASSWORD`                 | required in Docker    | PostgreSQL password                                 |
| `SECRET_KEY`                  | required              | Random key used to sign JWT                         |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080`               | JWT lifetime in minutes                             |
| `HF_TOKEN`                    | remote inference      | Token with the `Inference Providers` permission     |
| `HF_INFERENCE_PROVIDER`       | `featherless-ai`      | Provider Hugging Face per i modelli remoti iniziali |
| `HERMES_INBOX`                | `./uploads_web`       | Folder watched for incoming CSV files               |
| `HERMES_ARCHIVE`              | `./processed`         | Destination for successfully processed files        |
| `HERMES_FAILED`               | `./failed`            | Destination for files that exceeded max retries     |
| `HERMES_INTERRUPTED`          | `./interrupted`       | Destination for interrupted files                   |
| `HERMES_POLL_INTERVAL`        | `60`                  | Seconds between each scan of the inbox              |
| `HERMES_CHUNK_SIZE`           | `1000`                | Number of rows per chunk (Pandas chunksize)         |
| `HERMES_MAX_WORKERS`          | `4`                   | Max parallel threads in the ThreadPoolExecutor      |
| `HERMES_MAX_RETRIES`          | `3`                   | Max retry attempts before moving to failed          |
| `HERMES_WORKER_CLASS`         | `HybridWorker`        | Import path of the worker implementation            |
| `HERMES_AI_BASE_URL`          | local URL             | Endpoint for an OpenAI-compatible local server      |

The complete, sanitized template is tracked in `.env.example`. The legacy
variable `HUGGING_FACE` is temporarily accepted, but new configurations must
use `HF_TOKEN`. The initial Qwen model is served through Featherless AI, so
`HF_INFERENCE_PROVIDER=featherless-ai` selects it explicitly. `auto` remains
available for models whose provider can be selected automatically.

---

## Extending Hermes — Custom Workers

Hermes is designed to be **pluggable**. The processing logic lives in a single class that implements `WorkerBase`. You never touch the core pipeline.

### 1. Implement `WorkerBase`

```python
# my_project/my_worker.py
import pandas as pd
from hermes.worker_base import WorkerBase

class MyWorker(WorkerBase):
    def process(self, chunk: pd.DataFrame, metadata: dict) -> dict:
        """
        Args:
            chunk:    a pandas DataFrame slice of the original CSV
            metadata: dict with keys: filename, chunk_index, timestamp
        Returns:
            dict with at least: status ('ok' | 'error'), and any result data
        """
        # 1. Format your prompt from the chunk
        prompt = self._build_prompt(chunk)

        # 2. Call your AI API
        response = self._call_ai(prompt)

        # 3. Return structured result
        return {"status": "ok", "response": response, **metadata}

    def _build_prompt(self, chunk: pd.DataFrame) -> str:
        rows = chunk.to_csv(index=False)
        return f"Process the following data:\n\n{rows}"

    def _call_ai(self, prompt: str) -> str:
        # Your AI API client here
        ...
```

### 2. Register your worker in `.env`

```env
HERMES_WORKER_CLASS=my_project.my_worker.MyWorker
```

Hermes dynamically imports and instantiates the class at startup — no changes to core code required.

---

## Processing Loop

Each iteration of the Hermes loop follows these steps:

```
STEP 1 — Poll INBOX
  └─ No files found?  →  sleep(POLL_INTERVAL)  →  back to STEP 1
  └─ Files found?     →  pick oldest (FIFO)    →  STEP 2

STEP 2 — Atomic Move
  └─ os.rename(INBOX/file.csv, ARCHIVE/file.csv)
  └─ Rename failed?   →  log + skip            →  back to STEP 1

STEP 3 — Chunked Read
  └─ pd.read_csv(ARCHIVE/file.csv, chunksize=CHUNK_SIZE)
  └─ Parse error?     →  move to FAILED        →  back to STEP 1

STEP 4 — Dispatch
  └─ For each chunk:
       executor.submit(worker.process, chunk, metadata)  [non-blocking]
  └─ All chunks submitted                      →  back to STEP 1
```

On `SIGTERM` or `KeyboardInterrupt`, Hermes completes dispatch of the current file's chunks before exiting. No file is left in a partial state.

---

## Logging

Hermes uses Python's standard `logging` library with a structured format:

```
[HERMES] file=sales_jan.csv status=detected
[HERMES] file=sales_jan.csv status=moved_to_archive
[HERMES] file=sales_jan.csv chunk=0 status=dispatched rows=1000
[HERMES] file=sales_jan.csv chunk=1 status=dispatched rows=1000
[HERMES] file=sales_jan.csv chunk=2 status=dispatched rows=342
[HERMES] file=sales_jan.csv all_chunks=3 status=complete
[HERMES] file=sales_jan.csv chunk=1 status=worker_error retry=1/3
```

---

## GUI Control Room & Multi-Pool Management

Hermes offers a hybrid desktop dashboard to visually monitor and orchestrate the system:

- **Live Engine Status**: Start and stop the main polling loop.
- **Dynamic Thread Pool Management**:
  - Add new dedicated pools (e.g., `test_llm`, `production`) specifying the number of workers.
  - Hot-swap / Rename or resize workers without restarting the engine.
  - Delete no longer needed pools (queued tasks will be cancelled).
  - **Failsafe**: It is always mandatory to have at least one active pool if the engine is online. If a deleted/non-existent pool is requested, the system automatically redirects the task to the first available pool in the list (fallback).
- **Integrated Log Terminal**: Logs sent in real-time via WebSocket with timestamps.
- **Log Export**: Download a clean `.txt` file with header, with the ability to filter rows by start/end date and time.

---

## Testing

Hermes ships with a unit test suite covering all core modules. Unit tests run
in isolation with SQLite and mocked external services. The canonical Alembic
migration is additionally verified against a real PostgreSQL container with
`alembic upgrade`, `downgrade` and `check`.

### Test Stack

| Tool                 | Role                                     |
| -------------------- | ---------------------------------------- |
| `pytest`             | Test runner                              |
| `pytest-cov`         | Coverage reporting                       |
| `pytest-mock`        | Mock / patching utilities                |
| `SQLite (in-memory)` | Replaces PostgreSQL for DB tests         |
| `unittest.mock`      | Patches external I/O (HuggingFace, HTTP) |

### Test Structure

```
test/
├── conftest.py               # Shared fixtures (SQLite in-memory DB, transactional sessions)
├── test_main.py              # parse_cli_args, signal_handler, process_inbox
├── api/
│   └── test_health.py        # HealthCheckHandler (200 /health, 404, server start)
├── core/
│   ├── test_config.py        # Default values, init_directories (create + idempotent)
│   ├── test_mover.py         # move_file (atomic move, path return, OSError propagation)
│   ├── test_reader.py        # read_chunks (chunk size, all rows, columns, empty CSV)
│   └── test_watcher.py       # get_next_file (FIFO, non-CSV ignored, error → None)
├── db/
│   └── test_repository.py    # get_execution_context (fields, ValueError, defaults)
│                             # save_result (fields, multiple results, stato Errore)
├── gui/
│   ├── test_state.py         # WsLogHandler (buffer, trimming, WS send/remove)
│   ├── test_control_route.py # /api/* routes: status, CRUD pool, CRUD routes, start/stop
│   ├── test_dashboard_route.py # GET / → HTML 200
│   └── test_logs_route.py    # /api/logs/download (filtri, 400, Content-Disposition)
└── workers/
    ├── test_ai_worker.py     # LocalAIWorker (_is_token_valid cache/network,
    │                         #   _call_ai params, process cancel/DB error/token error)
    ├── test_dispatcher.py    # Dispatcher (add/remove/update pool, submit_chunk,
    │                         #   fallback, stats, full routing table CRUD)
    └── test_worker_base.py   # FatalWorkerError, WorkerBase ABC enforcement
```

### Running the Tests

Using `uv` (Recommended):

```bash
uv run pytest
```

Using python directly:

```bash
python -m pytest
```

Run a specific module:

```bash
uv run pytest test/workers/test_dispatcher.py -v
```

### Coverage

The HTML coverage report is automatically generated in `htmlcov/` after each run.

| Module                        | Coverage |
| ----------------------------- | -------- |
| `src/core/config.py`          | 100%     |
| `src/core/mover.py`           | 100%     |
| `src/core/reader.py`          | 100%     |
| `src/core/watcher.py`         | 100%     |
| `src/db/repository.py`        | 100%     |
| `src/db/models.py`            | 100%     |
| `src/gui/routes/__init__.py`  | 100%     |
| `src/gui/routes/dashboard.py` | 100%     |
| `src/gui/state.py`            | 100%     |
| `src/api/health.py`           | 95%      |
| `src/gui/routes/control.py`   | 95%      |
| `src/workers/ai_worker.py`    | 94%      |
| `src/workers/dispatcher.py`   | 95%      |
| `src/gui/routes/logs.py`      | 77%      |
| `src/main.py`                 | 59%      |
| **TOTAL**                     | **84%**  |

> **Note:** `src/gui/app.py` and `src/main.py` contain code that launches real threads, web servers, and desktop windows (PyWebView/uvicorn). These are integration-level concerns excluded from the unit test scope.

---

## Roadmap

- [x] Core polling loop
- [x] Atomic file move
- [x] Pandas chunked reading
- [x] ThreadPoolExecutor dispatch
- [x] Pluggable `WorkerBase` interface
- [x] Retry with exponential backoff (`tenacity`)
- [x] Health check HTTP endpoint
- [x] GUI Dashboard (FastAPI + PyWebView)
- [x] Dynamic `MAX_WORKERS` & Multi-Pool reload without restart
- [x] Prometheus metrics exporter
- [x] PostgreSQL Database Integration
- [x] Docker + docker-compose setup
- [x] Unit test suite (153 tests, 84% overall coverage, 100% on core modules)

---

## License

Apache License 2.0
