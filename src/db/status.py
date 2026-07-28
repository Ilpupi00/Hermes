from enum import StrEnum


class JobStatus(StrEnum):
    DRAFT = "Bozza"
    QUEUED = "In attesa"
    RUNNING = "In corso"
    COMPLETED = "Completato"
    FAILED = "Fallito"
    DEFERRED = "Rimandato"
    CANCELLED = "Annullato"


class ResultStatus(StrEnum):
    COMPLETED = "Completato"
    ERROR = "Errore"


JOB_STATUS_VALUES = tuple(status.value for status in JobStatus)
RESULT_STATUS_VALUES = tuple(status.value for status in ResultStatus)


ALLOWED_JOB_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.DRAFT: frozenset({JobStatus.QUEUED, JobStatus.CANCELLED}),
    JobStatus.QUEUED: frozenset(
        {JobStatus.RUNNING, JobStatus.CANCELLED, JobStatus.FAILED}
    ),
    JobStatus.RUNNING: frozenset(
        {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.DEFERRED,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.DEFERRED: frozenset(
        {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.CANCELLED}
    ),
    JobStatus.COMPLETED: frozenset(),
    JobStatus.FAILED: frozenset({JobStatus.QUEUED}),
    JobStatus.CANCELLED: frozenset(),
}


def can_transition(current: JobStatus, target: JobStatus) -> bool:
    return current == target or target in ALLOWED_JOB_TRANSITIONS[current]
