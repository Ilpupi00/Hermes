import pytest

from src.db.status import (
    JOB_STATUS_VALUES,
    RESULT_STATUS_VALUES,
    JobStatus,
    ResultStatus,
    can_transition,
)


def test_job_status_values_are_unique():
    assert len(JOB_STATUS_VALUES) == len(set(JOB_STATUS_VALUES))


def test_result_status_values_are_unique():
    assert len(RESULT_STATUS_VALUES) == len(set(RESULT_STATUS_VALUES))


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobStatus.DRAFT, JobStatus.QUEUED),
        (JobStatus.QUEUED, JobStatus.RUNNING),
        (JobStatus.RUNNING, JobStatus.COMPLETED),
        (JobStatus.RUNNING, JobStatus.FAILED),
        (JobStatus.RUNNING, JobStatus.DEFERRED),
        (JobStatus.DEFERRED, JobStatus.QUEUED),
        (JobStatus.FAILED, JobStatus.QUEUED),
    ],
)
def test_supported_job_transitions(current, target):
    assert can_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobStatus.DRAFT, JobStatus.COMPLETED),
        (JobStatus.QUEUED, JobStatus.COMPLETED),
        (JobStatus.COMPLETED, JobStatus.RUNNING),
        (JobStatus.CANCELLED, JobStatus.QUEUED),
    ],
)
def test_unsupported_job_transitions(current, target):
    assert not can_transition(current, target)


def test_same_state_is_idempotent():
    assert can_transition(JobStatus.RUNNING, JobStatus.RUNNING)


def test_public_state_values_remain_compatible():
    assert JobStatus.QUEUED.value == "In attesa"
    assert JobStatus.COMPLETED.value == "Completato"
    assert ResultStatus.ERROR.value == "Errore"
