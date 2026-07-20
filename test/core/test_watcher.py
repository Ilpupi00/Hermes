"""
Test unitari per src/core/watcher.py

Copre:
- get_next_file: inbox vuota → None, un solo file, FIFO (il più vecchio),
  solo .csv, errore os.scandir → None.
"""
import os
import time
import pytest
from pathlib import Path
from unittest.mock import patch

from src.core.watcher import get_next_file


class TestGetNextFile:
    def test_empty_inbox_returns_none(self, tmp_path):
        """Una directory vuota deve restituire None."""
        result = get_next_file(tmp_path)
        assert result is None

    def test_single_csv_is_returned(self, tmp_path):
        """Con un solo file .csv deve restituire il suo percorso."""
        csv = tmp_path / "file.csv"
        csv.write_text("data")

        result = get_next_file(tmp_path)

        assert result == csv

    def test_returns_oldest_csv_first(self, tmp_path):
        """Deve restituire il file con mtime più basso (il più vecchio — FIFO)."""
        old_file = tmp_path / "old.csv"
        old_file.write_text("old")
        # Impostiamo un mtime artificialmente nel passato
        os.utime(old_file, (0, 0))

        new_file = tmp_path / "new.csv"
        new_file.write_text("new")

        result = get_next_file(tmp_path)

        assert result == old_file

    def test_non_csv_files_are_ignored(self, tmp_path):
        """File con estensione diversa da .csv non devono essere considerati."""
        (tmp_path / "notes.txt").write_text("ignore me")
        (tmp_path / "archive.zip").write_text("ignore me too")

        result = get_next_file(tmp_path)

        assert result is None

    def test_mixed_files_returns_only_csv(self, tmp_path):
        """In presenza di file misti, deve restituire solo un .csv."""
        (tmp_path / "notes.txt").write_text("txt")
        csv = tmp_path / "data.csv"
        csv.write_text("csv")

        result = get_next_file(tmp_path)

        assert result == csv

    def test_returns_none_on_scandir_error(self, tmp_path):
        """Se os.scandir solleva un'eccezione, deve restituire None (non crashare)."""
        with patch("src.core.watcher.os.scandir", side_effect=PermissionError("denied")):
            result = get_next_file(tmp_path)

        assert result is None

    def test_result_is_path_instance(self, tmp_path):
        """Il valore restituito deve essere un'istanza di pathlib.Path."""
        (tmp_path / "input.csv").write_text("data")

        result = get_next_file(tmp_path)

        assert isinstance(result, Path)
