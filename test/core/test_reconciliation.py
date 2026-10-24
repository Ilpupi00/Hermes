"""Test di integrazione per la riconciliazione PostgreSQL/filesystem."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from src.core import reconciliation
from src.core.job_file import build_job_filename
from src.db import repository
from src.db.models import Esecuzione, ModelloLLM, RigaInput, Task, Utente
from src.db.status import JobStatus


NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    directories = {
        "inbox": tmp_path / "uploads_web",
        "processing": tmp_path / "processing",
        "archive": tmp_path / "processed",
        "failed": tmp_path / "failed",
        "interrupted": tmp_path / "interrupted",
    }
    for directory in directories.values():
        directory.mkdir()

    monkeypatch.setattr(reconciliation.config, "INBOX", directories["inbox"])
    monkeypatch.setattr(
        reconciliation.config, "PROCESSING", directories["processing"]
    )
    monkeypatch.setattr(
        reconciliation.config, "ARCHIVE", directories["archive"]
    )
    monkeypatch.setattr(reconciliation.config, "FAILED", directories["failed"])
    monkeypatch.setattr(
        reconciliation.config, "INTERRUPTED", directories["interrupted"]
    )
    monkeypatch.setattr(reconciliation.config, "ORPHAN_GRACE_SECONDS", 300)
    return directories


@pytest.fixture
def reconciler_db(db_session, monkeypatch):
    @contextmanager
    def session_factory():
        yield db_session

    monkeypatch.setattr(reconciliation, "SessionLocal", session_factory)
    return db_session


def _create_job(db, status: JobStatus, age_seconds: int = 600, rows: int = 2):
    user = Utente(
        username="reconciliation-user",
        email="reconciliation@hermes.local",
        password="test-password",
    )
    model = ModelloLLM(nome_modello="test/reconciliation-model")
    db.add_all([user, model])
    db.flush()

    created_at = (NOW - timedelta(seconds=age_seconds)).replace(tzinfo=None)
    task = Task(
        id_utente=user.id_utente,
        id_modello=model.id_modello,
        nome="Reconciliation test",
        stato=status.value,
        data_creazione=created_at,
    )
    db.add(task)
    db.flush()

    file_csv = repository.create_input_file(
        db,
        "input.csv",
        [{"review": f"row-{index}"} for index in range(rows)],
    )
    file_csv.data_caricamento = created_at
    execution = Esecuzione(
        id_task=task.id_task,
        id_file=file_csv.id_file,
        stato=status.value,
        totale_righe=rows,
    )
    db.add(execution)
    db.flush()
    return task, file_csv, execution


def _canonical(execution: Esecuzione) -> str:
    return build_job_filename(execution.id_esecuzione, execution.id_file)


def test_recovers_running_file_from_processing(
    reconciler_db, lifecycle
):
    _, _, execution = _create_job(reconciler_db, JobStatus.RUNNING)
    source = lifecycle["processing"] / _canonical(execution)
    source.write_text("review\nhello\n", encoding="utf-8")

    stats = reconciliation.reconcile_jobs(now=NOW)

    assert (lifecycle["inbox"] / source.name).is_file()
    assert not source.exists()
    assert execution.stato == JobStatus.QUEUED.value
    assert stats.recovered == 1
    assert stats.statuses_fixed == 1


def test_quarantines_file_without_database_execution(
    reconciler_db, lifecycle
):
    orphan = lifecycle["processing"] / "job_999_file_999.csv"
    orphan.write_text("review\norphan\n", encoding="utf-8")

    stats = reconciliation.reconcile_jobs(now=NOW)

    assert (lifecycle["failed"] / orphan.name).is_file()
    assert stats.quarantined == 1


def test_completed_job_is_archived_instead_of_replayed(
    reconciler_db, lifecycle
):
    _, _, execution = _create_job(reconciler_db, JobStatus.COMPLETED)
    source = lifecycle["interrupted"] / _canonical(execution)
    source.write_text("review\ncompleted\n", encoding="utf-8")

    reconciliation.reconcile_jobs(now=NOW)

    assert (lifecycle["archive"] / source.name).is_file()
    assert not (lifecycle["inbox"] / source.name).exists()
    assert execution.stato == JobStatus.COMPLETED.value


def test_old_active_record_without_file_is_failed(
    reconciler_db, lifecycle
):
    task, _, execution = _create_job(
        reconciler_db, JobStatus.QUEUED, age_seconds=600
    )

    stats = reconciliation.reconcile_jobs(now=NOW)

    assert execution.stato == JobStatus.FAILED.value
    assert task.stato == JobStatus.FAILED.value
    assert stats.statuses_fixed == 1


def test_recent_active_record_without_file_uses_grace_period(
    reconciler_db, lifecycle
):
    task, _, execution = _create_job(
        reconciler_db, JobStatus.QUEUED, age_seconds=30
    )

    stats = reconciliation.reconcile_jobs(now=NOW)

    assert execution.stato == JobStatus.QUEUED.value
    assert task.stato == JobStatus.QUEUED.value
    assert stats.skipped_recent == 1
    assert stats.statuses_fixed == 0


def test_stale_part_is_quarantined_and_job_failed(
    reconciler_db, lifecycle
):
    _, _, execution = _create_job(
        reconciler_db, JobStatus.QUEUED, age_seconds=600
    )
    staging = lifecycle["inbox"] / f".{_canonical(execution)}.abc123.part"
    staging.write_text("partial", encoding="utf-8")

    stats = reconciliation.reconcile_jobs(now=NOW)

    assert not staging.exists()
    assert any(lifecycle["failed"].glob("*.part"))
    assert execution.stato == JobStatus.FAILED.value
    assert stats.quarantined == 1


def test_complete_archive_repairs_database_status(
    reconciler_db, lifecycle
):
    _, file_csv, execution = _create_job(
        reconciler_db, JobStatus.RUNNING, rows=2
    )
    rows = (
        reconciler_db.query(RigaInput)
        .filter(RigaInput.id_file == file_csv.id_file)
        .order_by(RigaInput.indice_riga)
        .all()
    )
    for row in rows:
        repository.save_result(
            reconciler_db,
            execution.id_esecuzione,
            file_csv.id_file,
            row.id_riga_input,
            "ok",
            1.0,
            "Completato",
        )
    archived = lifecycle["archive"] / _canonical(execution)
    archived.write_text("review\none\ntwo\n", encoding="utf-8")

    reconciliation.reconcile_jobs(now=NOW)

    assert execution.stato == JobStatus.COMPLETED.value
    assert archived.is_file()


def test_incomplete_archive_is_failed_and_quarantined(
    reconciler_db, lifecycle
):
    _, _, execution = _create_job(
        reconciler_db, JobStatus.RUNNING, rows=2
    )
    archived = lifecycle["archive"] / _canonical(execution)
    archived.write_text("review\nonly-one\n", encoding="utf-8")

    reconciliation.reconcile_jobs(now=NOW)

    assert execution.stato == JobStatus.FAILED.value
    assert not archived.exists()
    assert (lifecycle["failed"] / archived.name).is_file()


def test_duplicate_processing_copy_is_quarantined_without_replacing_inbox(
    reconciler_db, lifecycle
):
    _, _, execution = _create_job(reconciler_db, JobStatus.RUNNING)
    filename = _canonical(execution)
    inbox = lifecycle["inbox"] / filename
    processing = lifecycle["processing"] / filename
    inbox.write_text("authoritative inbox", encoding="utf-8")
    processing.write_text("duplicate processing", encoding="utf-8")

    stats = reconciliation.reconcile_jobs(now=NOW)

    assert inbox.read_text(encoding="utf-8") == "authoritative inbox"
    assert not processing.exists()
    quarantined = list(lifecycle["failed"].glob("*.csv"))
    assert len(quarantined) == 1
    assert quarantined[0].read_text(encoding="utf-8") == "duplicate processing"
    assert execution.stato == JobStatus.QUEUED.value
    assert stats.quarantined == 1


def test_mismatched_file_id_is_quarantined_and_old_record_failed(
    reconciler_db, lifecycle
):
    _, file_csv, execution = _create_job(
        reconciler_db, JobStatus.QUEUED, age_seconds=600
    )
    mismatched = lifecycle["inbox"] / build_job_filename(
        execution.id_esecuzione, file_csv.id_file + 1
    )
    mismatched.write_text("wrong relation", encoding="utf-8")

    stats = reconciliation.reconcile_jobs(now=NOW)

    assert not mismatched.exists()
    assert (lifecycle["failed"] / mismatched.name).is_file()
    assert execution.stato == JobStatus.FAILED.value
    assert stats.quarantined == 1
    assert stats.statuses_fixed == 1


def test_failed_file_repairs_active_database_status(
    reconciler_db, lifecycle
):
    task, _, execution = _create_job(reconciler_db, JobStatus.RUNNING)
    failed = lifecycle["failed"] / _canonical(execution)
    failed.write_text("failed input", encoding="utf-8")

    reconciliation.reconcile_jobs(now=NOW)

    assert failed.is_file()
    assert execution.stato == JobStatus.FAILED.value
    assert task.stato == JobStatus.FAILED.value
