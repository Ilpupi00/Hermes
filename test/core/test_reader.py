"""
Test unitari per src/core/reader.py

Copre:
- read_chunks: lettura corretta di un CSV, ristpetto del chunk_size,
  propagazione delle eccezioni in caso di file non valido.
"""
import io
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.reader import read_chunks


CSV_CONTENT = "col_a,col_b\n1,a\n2,b\n3,c\n4,d\n5,e\n"


class TestReadChunks:
    def test_yields_dataframes(self, tmp_path):
        """read_chunks deve restituire un iteratore di DataFrame."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(CSV_CONTENT, encoding="utf-8")

        chunks = list(read_chunks(csv_file, chunk_size=10))

        assert len(chunks) > 0
        assert all(isinstance(c, pd.DataFrame) for c in chunks)

    def test_chunk_size_respected(self, tmp_path):
        """Ogni chunk non deve superare il chunk_size specificato."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(CSV_CONTENT, encoding="utf-8")

        chunks = list(read_chunks(csv_file, chunk_size=2))

        for chunk in chunks:
            assert len(chunk) <= 2

    def test_all_rows_are_returned(self, tmp_path):
        """La somma delle righe di tutti i chunk deve coprire tutto il file."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(CSV_CONTENT, encoding="utf-8")

        total_rows = sum(len(c) for c in read_chunks(csv_file, chunk_size=2))

        assert total_rows == 5  # CSV_CONTENT ha 5 righe dati

    def test_single_chunk_when_size_exceeds_rows(self, tmp_path):
        """Se chunk_size > righe totali, deve restituire un unico chunk."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(CSV_CONTENT, encoding="utf-8")

        chunks = list(read_chunks(csv_file, chunk_size=1000))

        assert len(chunks) == 1

    def test_correct_columns(self, tmp_path):
        """Le colonne del DataFrame devono corrispondere all'header del CSV."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(CSV_CONTENT, encoding="utf-8")

        chunk = next(iter(read_chunks(csv_file, chunk_size=10)))

        assert list(chunk.columns) == ["col_a", "col_b"]

    def test_raises_on_invalid_file(self, tmp_path):
        """Se il file non esiste, deve propagare l'eccezione."""
        missing_file = tmp_path / "nonexistent.csv"

        with pytest.raises(Exception):
            list(read_chunks(missing_file, chunk_size=10))

    def test_empty_csv_returns_empty_dataframe(self, tmp_path):
        """Un CSV con solo header produce un unico chunk DataFrame vuoto (0 righe)."""
        header_only = tmp_path / "empty.csv"
        header_only.write_text("col_a,col_b\n", encoding="utf-8")

        chunks = list(read_chunks(header_only, chunk_size=10))

        # pandas emette un DataFrame con 0 righe ma con le colonne dell'header
        assert len(chunks) == 1
        assert chunks[0].empty
        assert list(chunks[0].columns) == ["col_a", "col_b"]