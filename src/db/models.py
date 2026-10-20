from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from .db import Base
from .status import JOB_STATUS_VALUES, RESULT_STATUS_VALUES, JobStatus


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class Utente(Base):
    __tablename__ = "utenti"
    __table_args__ = (
        UniqueConstraint("username", name="uq_utenti_username"),
        UniqueConstraint("email", name="uq_utenti_email"),
    )

    id_utente = Column(Integer, Identity(), primary_key=True)
    username = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    hub_token = Column(String(255))


class Admin(Base):
    __tablename__ = "amministratori"
    __table_args__ = (
        UniqueConstraint("username", name="uq_amministratori_username"),
    )

    id = Column(Integer, Identity(), primary_key=True)
    username = Column(String(50), nullable=False)
    hashed_password = Column(String(255), nullable=False)


class ModelloLLM(Base):
    __tablename__ = "modellillm"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('hf_api', 'local_url', 'hf_local')",
            name="ck_modellillm_tipo",
        ),
        UniqueConstraint("nome_modello", "tipo", name="uq_modellillm_nome_tipo"),
    )

    id_modello = Column(Integer, Identity(), primary_key=True)
    nome_modello = Column(String(100), nullable=False)
    tipo = Column(
        String(20), nullable=False, default="hf_api", server_default="hf_api"
    )
    endpoint_url = Column(String(500))
    descrizione = Column(Text)


class Task(Base):
    __tablename__ = "task"
    __table_args__ = (
        CheckConstraint(
            f"stato IN ({_sql_values(JOB_STATUS_VALUES)})",
            name="ck_task_stato",
        ),
        CheckConstraint(
            "temperatura >= 0 AND temperatura <= 2",
            name="ck_task_temperatura",
        ),
        CheckConstraint("max_tokens > 0", name="ck_task_max_tokens"),
    )

    id_task = Column(Integer, Identity(), primary_key=True)
    id_utente = Column(
        Integer,
        ForeignKey("utenti.id_utente", ondelete="RESTRICT"),
        nullable=False,
    )
    id_modello = Column(
        Integer,
        ForeignKey("modellillm.id_modello", ondelete="RESTRICT"),
        nullable=False,
    )
    nome = Column(String(100), nullable=False)
    stato = Column(
        String(50),
        nullable=False,
        default=JobStatus.DRAFT.value,
        server_default=JobStatus.DRAFT.value,
    )
    prompt = Column(Text)
    dynamic_prompt = Column(Text)
    temperatura = Column(
        Float, nullable=False, default=0.1, server_default="0.1"
    )
    max_tokens = Column(
        Integer, nullable=False, default=500, server_default="500"
    )
    data_creazione = Column(DateTime, nullable=False, server_default=func.now())


class FileCSV(Base):
    __tablename__ = "filecsv"
    __table_args__ = (
        CheckConstraint("numero_righe >= 0", name="ck_filecsv_numero_righe"),
    )

    id_file = Column(Integer, Identity(), primary_key=True)
    nome_file = Column(String(255), nullable=False)
    numero_righe = Column(Integer, nullable=False)
    data_caricamento = Column(DateTime, nullable=False, server_default=func.now())


class Mapping(Base):
    __tablename__ = "mapping"
    __table_args__ = (
        UniqueConstraint(
            "id_task", "placeholder_prompt", name="uq_mapping_task_placeholder"
        ),
    )

    id_mapping = Column(Integer, Identity(), primary_key=True)
    id_task = Column(
        Integer,
        ForeignKey("task.id_task", ondelete="CASCADE"),
        nullable=False,
    )
    colonna_csv = Column(String(100), nullable=False)
    placeholder_prompt = Column(String(100), nullable=False)


class RigaInput(Base):
    __tablename__ = "righeinput"
    __table_args__ = (
        UniqueConstraint("id_file", "indice_riga", name="uq_righeinput_file_indice"),
    )

    id_riga_input = Column(Integer, Identity(), primary_key=True)
    id_file = Column(
        Integer,
        ForeignKey("filecsv.id_file", ondelete="CASCADE"),
        nullable=False,
    )
    indice_riga = Column(Integer, nullable=False)
    contenuto = Column(Text, nullable=False)


class Esecuzione(Base):
    __tablename__ = "esecuzione"
    __table_args__ = (
        CheckConstraint(
            f"stato IN ({_sql_values(JOB_STATUS_VALUES)})",
            name="ck_esecuzione_stato",
        ),
        CheckConstraint("totale_righe >= 0", name="ck_esecuzione_totale_righe"),
    )

    id_esecuzione = Column(Integer, Identity(), primary_key=True)
    id_task = Column(
        Integer,
        ForeignKey("task.id_task", ondelete="CASCADE"),
        nullable=False,
    )
    id_file = Column(
        Integer,
        ForeignKey("filecsv.id_file", ondelete="SET NULL"),
        nullable=True,
    )
    stato = Column(
        String(50),
        nullable=False,
        default=JobStatus.QUEUED.value,
        server_default=JobStatus.QUEUED.value,
    )
    data_inizio = Column(DateTime)
    data_fine = Column(DateTime)
    totale_righe = Column(
        Integer, nullable=False, default=0, server_default="0"
    )


class Risultato(Base):
    __tablename__ = "risultato"
    __table_args__ = (
        CheckConstraint(
            f"stato IN ({_sql_values(RESULT_STATUS_VALUES)})",
            name="ck_risultato_stato",
        ),
        CheckConstraint(
            "tempo_esecuzione IS NULL OR tempo_esecuzione >= 0",
            name="ck_risultato_tempo",
        ),
        UniqueConstraint(
            "id_esecuzione",
            "id_riga_input",
            name="uq_risultato_esecuzione_riga",
        ),
    )

    id_risultato = Column(Integer, Identity(), primary_key=True)
    id_esecuzione = Column(
        Integer,
        ForeignKey("esecuzione.id_esecuzione", ondelete="CASCADE"),
        nullable=False,
    )
    id_riga_input = Column(
        Integer,
        ForeignKey("righeinput.id_riga_input", ondelete="SET NULL"),
        nullable=True,
    )
    id_file = Column(
        Integer,
        ForeignKey("filecsv.id_file", ondelete="SET NULL"),
        nullable=True,
    )
    output = Column(Text)
    tempo_esecuzione = Column(Float)
    stato = Column(String(50), nullable=False)
