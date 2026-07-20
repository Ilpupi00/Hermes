"""
Fixtures condivise per l'intera test suite di Hermes.

Usa SQLite in-memory tramite SQLAlchemy per isolare i test
dal database PostgreSQL di produzione.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Importiamo Base dai models per poter creare le tabelle in-memory
from src.db.models import Base


@pytest.fixture(scope="session")
def engine():
    """Crea un engine SQLite in-memory condiviso per la sessione di test."""
    _engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(_engine)
    yield _engine
    _engine.dispose()


@pytest.fixture()
def db_session(engine):
    """
    Fornisce una sessione di database transazionale.
    Ogni test lavora all'interno di una transazione che viene
    sempre ritirata (rollback) al termine, garantendo isolamento.
    """
    connection = engine.connect()
    transaction = connection.begin()

    SessionFactory = sessionmaker(bind=connection)
    session = SessionFactory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
