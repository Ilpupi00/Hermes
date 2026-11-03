"""Integration tests for the minimum CSV upload persistence flow."""

import threading

import pytest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.db import repository
from src.db.models import (
    Esecuzione,
    FileCSV,
    Mapping,
    ModelloLLM,
    RigaInput,
    Task,
    Utente,
)
from src.db.status import JobStatus
from src.core.job_file import build_job_filename
from src.gui.routes.upload import router
import src.main as hermes_main


@pytest.fixture(autouse=True)
def reset_cancellation_registry():
    hermes_main.active_cancel_events.clear()
    hermes_main.requested_cancellations.clear()
    hermes_main.shutdown_interruptions.clear()
    yield
    hermes_main.active_cancel_events.clear()
    hermes_main.requested_cancellations.clear()
    hermes_main.shutdown_interruptions.clear()


def test_upload_persists_file_rows_and_execution_link(db_session, tmp_path):
    model = ModelloLLM(
        nome_modello="local-smoke-model",
        tipo="local_url",
        endpoint_url="http://localhost:11434/v1",
    )
    db_session.add(model)
    db_session.flush()

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    session_context = MagicMock()
    session_context.__enter__ = MagicMock(return_value=db_session)
    session_context.__exit__ = MagicMock(return_value=False)

    inbox = tmp_path / "inbox"
    processing = tmp_path / "processing"
    archive = tmp_path / "processed"
    failed = tmp_path / "failed"
    interrupted = tmp_path / "interrupted"
    cancelled = tmp_path / "cancelled"

    with (
        patch(
            "src.gui.routes.upload.SessionLocal",
            return_value=session_context,
        ),
        patch("src.gui.routes.upload.config.INBOX", inbox),
        patch("src.gui.routes.upload.config.PROCESSING", processing),
        patch("src.gui.routes.upload.config.ARCHIVE", archive),
        patch("src.gui.routes.upload.config.FAILED", failed),
        patch("src.gui.routes.upload.config.INTERRUPTED", interrupted),
        patch("src.gui.routes.upload.config.CANCELLED", cancelled),
        patch("src.gui.routes.upload.config.MAX_WORKERS", 99),
    ):
        response = client.post(
            "/api/upload",
            data={
                "id_modello": str(model.id_modello),
                "prompt": "Classifica {review}.",
                "temperatura": "0.1",
                "max_tokens": "50",
                "chunk_size": "3",
            },
            files={
                "file": (
                    "reviews.csv",
                    b"id,review\n1,ottimo\n2,pessimo\n3,nella media\n",
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()

    file_csv = db_session.get(FileCSV, payload["id_file"])
    execution = db_session.get(Esecuzione, payload["id_esecuzione"])
    rows = (
        db_session.query(RigaInput)
        .filter(RigaInput.id_file == payload["id_file"])
        .order_by(RigaInput.indice_riga)
        .all()
    )
    mappings = (
        db_session.query(Mapping)
        .filter(Mapping.id_task == execution.id_task)
        .all()
    )

    assert file_csv.nome_file == "reviews.csv"
    assert file_csv.numero_righe == 3
    assert execution.id_file == file_csv.id_file
    assert execution.totale_righe == 3
    assert execution.chunk_size == payload["chunk_size"]
    # Il valore del job non dipende dal numero di worker del processo web.
    assert execution.chunk_size == 3
    assert [row.indice_riga for row in rows] == [0, 1, 2]
    assert '"review": "ottimo"' in rows[0].contenuto
    assert len(mappings) == 1
    assert mappings[0].placeholder_prompt == "review"
    assert mappings[0].colonna_csv == "review"
    assert (inbox / payload["filename"]).read_bytes().startswith(b"id,review")
    assert not list(inbox.glob("*.part"))


def test_upload_rejects_non_positive_chunk_size(tmp_path):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/upload",
        data={
            "id_modello": "1",
            "prompt": "Classifica {review}.",
            "chunk_size": "0",
        },
        files={
            "file": (
                "reviews.csv",
                b"review\nottimo\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "chunk_size deve essere almeno 1"
    assert not (tmp_path / "inbox").exists()


@pytest.mark.parametrize(
    ("prompt", "csv_content", "expected_detail"),
    [
        (
            "Classifica {missing_column}.",
            b"id,review\n1,ottimo\n",
            "missing_column",
        ),
        (
            "Classifica {review}.",
            b"id,review\n1,\n",
            "riga 2, colonna review",
        ),
    ],
)
def test_upload_rejects_invalid_prompt_data(
    db_session,
    tmp_path,
    prompt,
    csv_content,
    expected_detail,
):
    model = ModelloLLM(
        nome_modello="local-validation-model",
        tipo="local_url",
        endpoint_url="http://localhost:11434/v1",
    )
    db_session.add(model)
    db_session.flush()

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    session_context = MagicMock()
    session_context.__enter__ = MagicMock(return_value=db_session)
    session_context.__exit__ = MagicMock(return_value=False)

    inbox = tmp_path / "inbox"
    with (
        patch(
            "src.gui.routes.upload.SessionLocal",
            return_value=session_context,
        ),
        patch("src.gui.routes.upload.config.INBOX", inbox),
    ):
        response = client.post(
            "/api/upload",
            data={
                "id_modello": str(model.id_modello),
                "prompt": prompt,
            },
            files={"file": ("reviews.csv", csv_content, "text/csv")},
        )

    assert response.status_code == 422
    assert expected_detail in response.json()["detail"]
    assert not inbox.exists()


def _create_job(db_session, status: JobStatus):
    user = Utente(
        username=f"cancel-{status.name.lower()}",
        email=f"cancel-{status.name.lower()}@hermes.local",
        password="test-password",
    )
    model = ModelloLLM(nome_modello=f"cancel/{status.name.lower()}")
    db_session.add_all([user, model])
    db_session.flush()
    task = Task(
        id_utente=user.id_utente,
        id_modello=model.id_modello,
        nome="Cancellation test",
        stato=status.value,
    )
    db_session.add(task)
    db_session.flush()
    file_csv = repository.create_input_file(
        db_session, "cancel.csv", [{"review": "ottimo"}]
    )
    execution = Esecuzione(
        id_task=task.id_task,
        id_file=file_csv.id_file,
        stato=status.value,
        totale_righe=1,
    )
    db_session.add(execution)
    db_session.flush()
    return task, file_csv, execution


def _session_context(db_session):
    context = MagicMock()
    context.__enter__ = MagicMock(return_value=db_session)
    context.__exit__ = MagicMock(return_value=False)
    return context


def test_cancel_queued_job_moves_file_and_preserves_record(db_session, tmp_path):
    task, file_csv, execution = _create_job(db_session, JobStatus.QUEUED)
    inbox = tmp_path / "uploads_web"
    cancelled = tmp_path / "cancelled"
    inbox.mkdir()
    filename = build_job_filename(execution.id_esecuzione, file_csv.id_file)
    (inbox / filename).write_text("review\nottimo\n", encoding="utf-8")

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    with (
        patch("src.gui.routes.upload.SessionLocal", return_value=_session_context(db_session)),
        patch("src.gui.routes.upload.config.INBOX", inbox),
        patch("src.gui.routes.upload.config.INTERRUPTED", tmp_path / "interrupted"),
        patch("src.gui.routes.upload.config.PROCESSING", tmp_path / "processing"),
        patch("src.gui.routes.upload.config.CANCELLED", cancelled),
    ):
        response = client.post(f"/api/jobs/{execution.id_esecuzione}/cancel")

    assert response.status_code == 202
    assert response.json()["status"] == "cancelled"
    assert (cancelled / filename).is_file()
    assert db_session.get(Esecuzione, execution.id_esecuzione).stato == JobStatus.CANCELLED.value
    assert db_session.get(Task, task.id_task).stato == JobStatus.CANCELLED.value
    assert db_session.get(FileCSV, file_csv.id_file) is not None


def test_cancel_running_job_signals_worker_without_deleting_data(db_session):
    task, file_csv, execution = _create_job(db_session, JobStatus.RUNNING)
    cancel_event = threading.Event()
    hermes_main.active_cancel_events[execution.id_esecuzione] = cancel_event

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    with patch(
        "src.gui.routes.upload.SessionLocal",
        return_value=_session_context(db_session),
    ):
        response = client.post(f"/api/jobs/{execution.id_esecuzione}/cancel")

    assert response.status_code == 202
    assert response.json()["status"] == "cancellation_requested"
    assert cancel_event.is_set()
    assert db_session.get(Esecuzione, execution.id_esecuzione).stato == JobStatus.RUNNING.value
    assert db_session.get(Task, task.id_task) is not None
    assert db_session.get(FileCSV, file_csv.id_file) is not None
