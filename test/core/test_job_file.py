import pytest

from src.core.job_file import build_job_filename, parse_job_filename


def test_build_and_parse_job_filename():
    filename = build_job_filename(12, 34)

    assert filename == "job_12_file_34.csv"
    assert parse_job_filename(filename).execution_id == 12
    assert parse_job_filename(filename).file_id == 34


@pytest.mark.parametrize(
    "filename",
    [
        "exec_12_file_34.csv",
        "job_0_file_34.csv",
        "job_12_file_0.csv",
        "job_12_file_34.csv.part",
        "job_12_file_34.CSV",
        "job_12_file_34_extra.csv",
    ],
)
def test_parse_rejects_non_canonical_names(filename):
    with pytest.raises(ValueError, match="Nome file non valido"):
        parse_job_filename(filename)


def test_build_rejects_non_positive_ids():
    with pytest.raises(ValueError, match="positivi"):
        build_job_filename(0, 1)
