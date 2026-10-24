"""Riconcilia il ciclo di vita dei job tra PostgreSQL e filesystem."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import config
from .job_file import build_job_filename, parse_job_filename
from .mover import move_file
from ..db import repository
from ..db.db import SessionLocal
from ..db.status import JobStatus


@dataclass
class ReconciliationStats:
    recovered: int = 0
    quarantined: int = 0
    statuses_fixed: int = 0
    skipped_recent: int = 0


def _commit_status(db, execution_id: int, status: JobStatus) -> None:
    repository.set_task_status_by_execution(db, execution_id, status.value)
    db.commit()


def _quarantine(path: Path, reason: str) -> Path:
    """Conserva un file anomalo in failed senza sovrascriverne altri."""
    target = config.FAILED / path.name
    if target.exists():
        suffix = path.suffix or ".file"
        target = config.FAILED / (
            f"{path.stem}.{reason}.{uuid4().hex[:8]}{suffix}"
        )
        path.replace(target)
        config.logger.info(
            f"file={path.name} status=quarantined reason={reason} "
            f"target={target.name}"
        )
        return target

    return move_file(path, config.FAILED)


def _move_lifecycle(path: Path, destination: Path, reason: str) -> Path:
    target = destination / path.name
    if target.exists():
        return _quarantine(path, f"duplicate_{reason}")
    return move_file(path, destination)


def _state_for_file(db, path: Path):
    try:
        ids = parse_job_filename(path.name)
    except ValueError as error:
        config.logger.error(
            f"status=reconciliation_invalid_filename file={path.name} "
            f"reason='{error}'"
        )
        return None, None

    state = repository.get_execution_reconciliation_state(db, ids.execution_id)
    if state is None:
        config.logger.error(
            f"status=reconciliation_orphan_file file={path.name} "
            "reason='esecuzione assente'"
        )
        return ids, None
    if state.file_id != ids.file_id:
        config.logger.error(
            f"status=reconciliation_file_mismatch file={path.name} "
            f"db_file_id={state.file_id}"
        )
        return ids, None
    return ids, state


def _reconcile_visible_files(db, stats: ReconciliationStats) -> None:
    sources = (
        (config.INBOX, "inbox"),
        (config.PROCESSING, "processing"),
        (config.INTERRUPTED, "interrupted"),
    )
    active_statuses = {
        JobStatus.QUEUED,
        JobStatus.RUNNING,
        JobStatus.DEFERRED,
    }

    for source, source_name in sources:
        for path in sorted(source.glob("*.csv")):
            _, state = _state_for_file(db, path)
            if state is None:
                _quarantine(path, "orphan")
                stats.quarantined += 1
                continue

            if state.status == JobStatus.COMPLETED:
                if source != config.ARCHIVE:
                    _move_lifecycle(path, config.ARCHIVE, "completed")
                    stats.recovered += 1
                continue

            if state.status in {JobStatus.FAILED, JobStatus.CANCELLED}:
                if source != config.FAILED:
                    _move_lifecycle(path, config.FAILED, "terminal")
                    stats.quarantined += 1
                continue

            if state.status == JobStatus.DRAFT:
                _quarantine(path, "draft")
                _commit_status(db, state.execution_id, JobStatus.FAILED)
                stats.quarantined += 1
                stats.statuses_fixed += 1
                continue

            if state.status in active_statuses:
                if source != config.INBOX:
                    target = config.INBOX / path.name
                    if target.exists():
                        _quarantine(path, f"duplicate_{source_name}")
                        stats.quarantined += 1
                        if state.status != JobStatus.QUEUED:
                            _commit_status(
                                db, state.execution_id, JobStatus.QUEUED
                            )
                            stats.statuses_fixed += 1
                        continue
                    move_file(path, config.INBOX)
                    stats.recovered += 1
                if state.status != JobStatus.QUEUED:
                    _commit_status(db, state.execution_id, JobStatus.QUEUED)
                    stats.statuses_fixed += 1


def _age_seconds(created_at: datetime, now: datetime) -> float:
    if created_at.tzinfo is not None:
        created_at = created_at.astimezone(UTC).replace(tzinfo=None)
    comparable_now = now.astimezone(UTC).replace(tzinfo=None)
    return max(0.0, (comparable_now - created_at).total_seconds())


def _staging_files(filename: str) -> list[Path]:
    return sorted(config.INBOX.glob(f".{filename}.*.part"))


def _reconcile_active_records(
    db,
    stats: ReconciliationStats,
    now: datetime,
) -> None:
    for state in repository.get_active_execution_reconciliation_states(db):
        if state.file_id is None:
            filename = None
            active_paths: list[Path] = []
            archived_path = None
            failed_path = None
            staging_paths: list[Path] = []
        else:
            filename = build_job_filename(state.execution_id, state.file_id)
            active_paths = [
                directory / filename
                for directory in (
                    config.INBOX,
                    config.PROCESSING,
                    config.INTERRUPTED,
                )
                if (directory / filename).exists()
            ]
            archived_path = config.ARCHIVE / filename
            failed_path = config.FAILED / filename
            staging_paths = _staging_files(filename)

        if active_paths:
            continue

        if archived_path is not None and archived_path.exists():
            if (
                state.total_rows > 0
                and state.completed_results == state.total_rows
            ):
                _commit_status(db, state.execution_id, JobStatus.COMPLETED)
            else:
                _move_lifecycle(
                    archived_path,
                    config.FAILED,
                    "incomplete_archive",
                )
                _commit_status(db, state.execution_id, JobStatus.FAILED)
            stats.statuses_fixed += 1
            continue

        if failed_path is not None and failed_path.exists():
            _commit_status(db, state.execution_id, JobStatus.FAILED)
            stats.statuses_fixed += 1
            continue

        age = _age_seconds(state.created_at, now)
        if age < config.ORPHAN_GRACE_SECONDS:
            stats.skipped_recent += 1
            config.logger.info(
                f"status=reconciliation_grace execution={state.execution_id} "
                f"age_seconds={age:.0f}"
            )
            continue

        for staging_path in staging_paths:
            _quarantine(staging_path, "stale_part")
            stats.quarantined += 1

        _commit_status(db, state.execution_id, JobStatus.FAILED)
        stats.statuses_fixed += 1
        config.logger.error(
            f"status=reconciliation_orphan_record execution={state.execution_id} "
            f"file={filename or 'missing_file_id'}"
        )


def reconcile_jobs(now: datetime | None = None) -> ReconciliationStats:
    """Ripristina le incoerenze sicure e mette in quarantena gli orfani."""
    config.init_directories()
    effective_now = now or datetime.now(UTC)
    stats = ReconciliationStats()

    config.logger.info(
        "status=reconciliation_started "
        f"orphan_grace_seconds={config.ORPHAN_GRACE_SECONDS}"
    )
    with SessionLocal() as db:
        _reconcile_visible_files(db, stats)
        _reconcile_active_records(db, stats, effective_now)

    config.logger.info(
        "status=reconciliation_completed "
        f"recovered={stats.recovered} quarantined={stats.quarantined} "
        f"statuses_fixed={stats.statuses_fixed} "
        f"skipped_recent={stats.skipped_recent}"
    )
    return stats
