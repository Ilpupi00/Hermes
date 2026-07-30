"""Integration tests for the minimum CSV upload persistence flow."""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.db.models import Esecuzione, FileCSV, ModelloLLM, RigaInput
from src.gui.routes.upload import router


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
    archive = tmp_path / "processed"
    failed = tmp_path / "failed"
    interrupted = tmp_path / "interrupted"

    with (
        patch(
            "src.gui.routes.upload.SessionLocal",
            return_value=session_context,
        ),
        patch("src.gui.routes.upload.config.INBOX", inbox),
        patch("src.gui.routes.upload.config.ARCHIVE", archive),
        patch("src.gui.routes.upload.config.FAILED", failed),
        patch("src.gui.routes.upload.config.INTERRUPTED", interrupted),
    ):
        response = client.post(
            "/api/upload",
            data={
                "id_modello": str(model.id_modello),
                "prompt": "Classifica la recensione.",
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

    assert file_csv.nome_file == "reviews.csv"
    assert file_csv.numero_righe == 3
    assert execution.id_file == file_csv.id_file
    assert execution.totale_righe == 3
    assert [row.indice_riga for row in rows] == [0, 1, 2]
    assert '"review": "ottimo"' in rows[0].contenuto
    assert (inbox / payload["filename"]).read_bytes().startswith(b"id,review")
