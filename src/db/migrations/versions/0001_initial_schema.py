"""Create the canonical Hermes schema and seed supported starter models.

Revision ID: 0001
Revises:
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_STATES = (
    "Bozza",
    "In attesa",
    "In corso",
    "Completato",
    "Fallito",
    "Rimandato",
    "Annullato",
)
RESULT_STATES = ("Completato", "Errore")


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "utenti",
        sa.Column("id_utente", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(100), nullable=False),
        sa.Column("password", sa.String(255), nullable=False),
        sa.Column("hub_token", sa.String(255)),
        sa.UniqueConstraint("username", name="uq_utenti_username"),
        sa.UniqueConstraint("email", name="uq_utenti_email"),
    )

    op.create_table(
        "amministratori",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.UniqueConstraint("username", name="uq_amministratori_username"),
    )

    op.create_table(
        "modellillm",
        sa.Column("id_modello", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("nome_modello", sa.String(100), nullable=False),
        sa.Column(
            "tipo", sa.String(20), nullable=False, server_default="hf_api"
        ),
        sa.Column("endpoint_url", sa.String(500)),
        sa.Column("descrizione", sa.Text()),
        sa.CheckConstraint(
            "tipo IN ('hf_api', 'local_url', 'hf_local')",
            name="ck_modellillm_tipo",
        ),
        sa.UniqueConstraint(
            "nome_modello", "tipo", name="uq_modellillm_nome_tipo"
        ),
    )

    op.create_table(
        "filecsv",
        sa.Column("id_file", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("nome_file", sa.String(255), nullable=False),
        sa.Column("numero_righe", sa.Integer(), nullable=False),
        sa.Column(
            "data_caricamento",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "numero_righe >= 0", name="ck_filecsv_numero_righe"
        ),
    )

    op.create_table(
        "task",
        sa.Column("id_task", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("id_utente", sa.Integer(), nullable=False),
        sa.Column("id_modello", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column(
            "stato", sa.String(50), nullable=False, server_default="Bozza"
        ),
        sa.Column("prompt", sa.Text()),
        sa.Column("dynamic_prompt", sa.Text()),
        sa.Column(
            "temperatura",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.1"),
        ),
        sa.Column(
            "max_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("500"),
        ),
        sa.Column(
            "data_creazione",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            f"stato IN ({_sql_values(JOB_STATES)})", name="ck_task_stato"
        ),
        sa.CheckConstraint(
            "temperatura >= 0 AND temperatura <= 2",
            name="ck_task_temperatura",
        ),
        sa.CheckConstraint("max_tokens > 0", name="ck_task_max_tokens"),
        sa.ForeignKeyConstraint(
            ["id_utente"],
            ["utenti.id_utente"],
            name="fk_task_utente",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["id_modello"],
            ["modellillm.id_modello"],
            name="fk_task_modello",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "mapping",
        sa.Column("id_mapping", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("id_task", sa.Integer(), nullable=False),
        sa.Column("colonna_csv", sa.String(100), nullable=False),
        sa.Column("placeholder_prompt", sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_task"],
            ["task.id_task"],
            name="fk_mapping_task",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "id_task", "placeholder_prompt", name="uq_mapping_task_placeholder"
        ),
    )

    op.create_table(
        "righeinput",
        sa.Column(
            "id_riga_input", sa.Integer(), sa.Identity(), primary_key=True
        ),
        sa.Column("id_file", sa.Integer(), nullable=False),
        sa.Column("indice_riga", sa.Integer(), nullable=False),
        sa.Column("contenuto", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_file"],
            ["filecsv.id_file"],
            name="fk_righeinput_file",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "id_file", "indice_riga", name="uq_righeinput_file_indice"
        ),
    )

    op.create_table(
        "esecuzione",
        sa.Column(
            "id_esecuzione", sa.Integer(), sa.Identity(), primary_key=True
        ),
        sa.Column("id_task", sa.Integer(), nullable=False),
        sa.Column("id_file", sa.Integer()),
        sa.Column(
            "stato",
            sa.String(50),
            nullable=False,
            server_default="In attesa",
        ),
        sa.Column("data_inizio", sa.DateTime()),
        sa.Column("data_fine", sa.DateTime()),
        sa.Column(
            "totale_righe",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.CheckConstraint(
            f"stato IN ({_sql_values(JOB_STATES)})",
            name="ck_esecuzione_stato",
        ),
        sa.CheckConstraint(
            "totale_righe >= 0", name="ck_esecuzione_totale_righe"
        ),
        sa.ForeignKeyConstraint(
            ["id_task"],
            ["task.id_task"],
            name="fk_esecuzione_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_file"],
            ["filecsv.id_file"],
            name="fk_esecuzione_file",
            ondelete="SET NULL",
        ),
    )

    op.create_table(
        "risultato",
        sa.Column(
            "id_risultato", sa.Integer(), sa.Identity(), primary_key=True
        ),
        sa.Column("id_esecuzione", sa.Integer(), nullable=False),
        sa.Column("id_riga_input", sa.Integer()),
        sa.Column("id_file", sa.Integer()),
        sa.Column("output", sa.Text()),
        sa.Column("tempo_esecuzione", sa.Float()),
        sa.Column("stato", sa.String(50), nullable=False),
        sa.CheckConstraint(
            f"stato IN ({_sql_values(RESULT_STATES)})",
            name="ck_risultato_stato",
        ),
        sa.CheckConstraint(
            "tempo_esecuzione IS NULL OR tempo_esecuzione >= 0",
            name="ck_risultato_tempo",
        ),
        sa.ForeignKeyConstraint(
            ["id_esecuzione"],
            ["esecuzione.id_esecuzione"],
            name="fk_risultato_esecuzione",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_riga_input"],
            ["righeinput.id_riga_input"],
            name="fk_risultato_riga",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["id_file"],
            ["filecsv.id_file"],
            name="fk_risultato_file",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "id_esecuzione",
            "id_riga_input",
            name="uq_risultato_esecuzione_riga",
        ),
    )

    models = sa.table(
        "modellillm",
        sa.column("nome_modello", sa.String()),
        sa.column("tipo", sa.String()),
        sa.column("endpoint_url", sa.String()),
        sa.column("descrizione", sa.Text()),
    )
    op.bulk_insert(
        models,
        [
            {
                "nome_modello": "Qwen/Qwen2.5-0.5B-Instruct",
                "tipo": "hf_api",
                "endpoint_url": None,
                "descrizione": "Primo modello remoto suggerito per Hermes.",
            },
            {
                "nome_modello": "apple/OpenELM-270M-Instruct",
                "tipo": "hf_local",
                "endpoint_url": None,
                "descrizione": "Modello Apple sperimentale per inferenza locale.",
            },
            {
                "nome_modello": "HuggingFaceTB/SmolLM2-360M-Instruct",
                "tipo": "hf_local",
                "endpoint_url": None,
                "descrizione": "Modello compatto per inferenza locale.",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("risultato")
    op.drop_table("esecuzione")
    op.drop_table("righeinput")
    op.drop_table("mapping")
    op.drop_table("task")
    op.drop_table("filecsv")
    op.drop_table("modellillm")
    op.drop_table("amministratori")
    op.drop_table("utenti")
