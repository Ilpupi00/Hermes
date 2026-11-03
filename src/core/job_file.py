"""Contratto del nome dei CSV scambiati tra webapp e motore Hermes."""

import re
from dataclasses import dataclass


_JOB_FILE_PATTERN = re.compile(
    r"^job_(?P<execution_id>[1-9]\d*)_file_(?P<file_id>[1-9]\d*)\.csv$"
)


@dataclass(frozen=True)
class JobFileIds:
    execution_id: int
    file_id: int


def build_job_filename(execution_id: int, file_id: int) -> str:
    """Costruisce il nome canonico di un CSV pronto per Hermes."""
    if execution_id < 1 or file_id < 1:
        raise ValueError("Gli identificativi di esecuzione e file devono essere positivi.")
    return f"job_{execution_id}_file_{file_id}.csv"


def parse_job_filename(filename: str) -> JobFileIds:
    """Estrae gli identificativi da un nome canonico, rifiutando varianti ambigue."""
    match = _JOB_FILE_PATTERN.fullmatch(filename)
    if not match:
        raise ValueError(
            "Nome file non valido: atteso job_{id_esecuzione}_file_{id_file}.csv"
        )
    return JobFileIds(
        execution_id=int(match.group("execution_id")),
        file_id=int(match.group("file_id")),
    )
