"""agregar receipt_scans

Revision ID: 5e6444609a53
Revises: f904ba67026c
Create Date: 2026-08-31 18:56:05.018567-03:00

Tabla de lecturas de ticket (docs/PROMPT.md §21.1). **No guarda la imagen**: la
foto se procesa en memoria y se descarta, así que acá solo quedan los campos
extraídos y la telemetría de la llamada.

Nota: el autogenerate propuso además catorce `alter_column` sobre los
`created_at` / `updated_at` de las tablas existentes. Se sacaron a mano: es el
falso positivo conocido de Alembic con MySQL, que compara `now()` contra
`(now())` y los toma por defaults distintos. Aplicarlos reescribiría todas las
tablas del esquema para dejarlas exactamente igual.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5e6444609a53"
down_revision: str | None = "f904ba67026c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "receipt_scans",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("EXTRACTED", "FAILED", "CONFIRMED", name="receipt_scan_status"),
            nullable=False,
        ),
        # Nullable: un ticket arrugado puede no tener monto legible, y guardar
        # la lectura parcial sirve para saber qué tan seguido pasa.
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("occurred_on", sa.Date(), nullable=True),
        sa.Column("merchant", sa.String(length=120), nullable=True),
        sa.Column("category_id", sa.BigInteger(), nullable=True),
        sa.Column("confidence", sa.JSON(), nullable=True),
        sa.Column("transaction_id", sa.BigInteger(), nullable=True),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("total_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_receipt_scans_user_created", "receipt_scans", ["user_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_receipt_scans_user_created", table_name="receipt_scans")
    op.drop_table("receipt_scans")
