"""
Test unitari per src/core/mover.py

Copre:
- move_file: spostamento atomico riuscito, restituzione del nuovo percorso,
  propagazione dell'eccezione in caso di errore.
"""
import pytest
from pathlib import Path
from unittest.mock import patch

from src.core.mover import move_file


class TestMoveFile:
    def test_file_is_moved(self, tmp_path):
        """Il file deve essere effettivamente presente nella destinazione."""
        source = tmp_path / "source.csv"
        source.write_text("data", encoding="utf-8")
        dest_dir = tmp_path / "archive"
        dest_dir.mkdir()

        move_file(source, dest_dir)

        assert (dest_dir / "source.csv").exists()
        assert not source.exists()

    def test_returns_destination_path(self, tmp_path):
        """move_file deve restituire il percorso completo del file spostato."""
        source = tmp_path / "report.csv"
        source.write_text("data", encoding="utf-8")
        dest_dir = tmp_path / "processed"
        dest_dir.mkdir()

        result = move_file(source, dest_dir)

        assert result == dest_dir / "report.csv"
        assert isinstance(result, Path)

    def test_raises_when_rename_fails(self, tmp_path):
        """Se os.rename solleva un'eccezione, move_file deve propagarla."""
        source = tmp_path / "bad.csv"
        source.write_text("data", encoding="utf-8")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with patch("src.core.mover.os.rename", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                move_file(source, dest_dir)

    def test_source_file_does_not_exist_after_move(self, tmp_path):
        """Dopo lo spostamento il file sorgente non deve più esistere."""
        source = tmp_path / "input.csv"
        source.write_text("content", encoding="utf-8")
        dest_dir = tmp_path / "done"
        dest_dir.mkdir()

        move_file(source, dest_dir)

        assert not source.exists()

    def test_file_content_preserved(self, tmp_path):
        """Il contenuto del file deve essere identico dopo lo spostamento."""
        content = "col_a,col_b\n1,hello\n"
        source = tmp_path / "data.csv"
        source.write_text(content, encoding="utf-8")
        dest_dir = tmp_path / "out"
        dest_dir.mkdir()

        dest = move_file(source, dest_dir)

        assert dest.read_text(encoding="utf-8") == content
