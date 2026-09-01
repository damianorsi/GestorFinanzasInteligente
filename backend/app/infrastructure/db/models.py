"""Modelos ORM de SQLAlchemy.

Son la representación de persistencia, distinta de las entidades de dominio:
`app/domain/entities/` no conoce SQLAlchemy y estos modelos no llevan reglas de
negocio. El mapeo entre ambos vive en `app/infrastructure/db/mappers.py`.

Convenciones de este esquema:

- El dinero es `DECIMAL(14, 2)`. Nunca `FLOAT` ni `DOUBLE`.
- Toda tabla con montos lleva `currency CHAR(3) NOT NULL DEFAULT 'ARS'` desde
  la primera migración, para que habilitar USD no sea un cambio de esquema.
- Las fechas de negocio son `DATE` (sin hora, sin zona). Los timestamps de
  auditoría son `DATETIME` en UTC.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    AlertStatus,
    AlertType,
    ChatRole,
    OccurrenceStatus,
    ReceiptScanStatus,
    RecurrenceFrequency,
    TransactionType,
)
from app.infrastructure.db.base import Base

PRECISION_MONTO = 14
ESCALA_MONTO = 2
LARGO_CODIGO_MONEDA = 3

# Opciones de tabla de MySQL comunes a todo el esquema.
_OPCIONES_MYSQL = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def _enum(enum_type: type, nombre: str) -> SAEnum:
    """Enum nativo de MySQL que persiste los *valores*, no los nombres.

    Sin `values_callable`, SQLAlchemy guarda el nombre del miembro. Con
    `StrEnum` coinciden, pero fijarlo explícitamente evita que renombrar un
    miembro cambie en silencio lo que hay en la base.
    """
    return SAEnum(
        enum_type,
        name=nombre,
        native_enum=True,
        values_callable=lambda e: [miembro.value for miembro in e],
    )


class TimestampMixin:
    """`created_at` / `updated_at` en UTC.

    La sesión de MySQL corre en UTC (ver docker-compose.yml), así que el
    `CURRENT_TIMESTAMP` de estos defaults ya es UTC.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


def _columna_moneda() -> Mapped[str]:
    """`CHAR(3)` y no `VARCHAR`: el código ISO 4217 es de largo fijo."""
    return mapped_column(CHAR(LARGO_CODIGO_MONEDA), nullable=False, server_default=text("'ARS'"))


def _columna_monto() -> Mapped[Decimal]:
    return mapped_column(Numeric(PRECISION_MONTO, ESCALA_MONTO), nullable=False)


# ---------------------------------------------------------------------------
# Usuarios y seguridad
# ---------------------------------------------------------------------------
class UserModel(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (_OPCIONES_MYSQL,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))


class RefreshTokenModel(Base):
    """Refresh tokens emitidos, para poder revocarlos.

    Se guarda el hash y no el token: si se filtra la base, los tokens
    almacenados no sirven para autenticarse.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_expires", "user_id", "expires_at"),
        _OPCIONES_MYSQL,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------
class CategoryModel(TimestampMixin, Base):
    """Categoría de clasificación. No lleva moneda: es transversal a todas."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name", "type", name="uq_categories_user_name_type"),
        _OPCIONES_MYSQL,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    type: Mapped[TransactionType] = mapped_column(
        _enum(TransactionType, "transaction_type"), nullable=False
    )
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"))


# ---------------------------------------------------------------------------
# Reglas recurrentes
# ---------------------------------------------------------------------------
class RecurringRuleModel(TimestampMixin, Base):
    __tablename__ = "recurring_rules"
    __table_args__ = (
        Index("ix_recurring_rules_user_active", "user_id", "is_active"),
        _OPCIONES_MYSQL,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    type: Mapped[TransactionType] = mapped_column(
        _enum(TransactionType, "transaction_type"), nullable=False
    )
    amount: Mapped[Decimal] = _columna_monto()
    currency: Mapped[str] = _columna_moneda()
    description: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("''"))
    frequency: Mapped[RecurrenceFrequency] = mapped_column(
        _enum(RecurrenceFrequency, "recurrence_frequency"), nullable=False
    )
    day_of_month: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    day_of_week: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))


# ---------------------------------------------------------------------------
# Movimientos
# ---------------------------------------------------------------------------
class TransactionModel(TimestampMixin, Base):
    """Un ingreso o gasto real.

    `category_id` es RESTRICT y no CASCADE a propósito: borrar una categoría
    con movimientos tiene que fallar, no llevarse el historial puesto.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_user_occurred", "user_id", "occurred_on"),
        Index("ix_transactions_user_category", "user_id", "category_id"),
        Index("ix_transactions_user_type", "user_id", "type"),
        # El índice que sostiene todas las agregaciones, que siempre filtran
        # por usuario y moneda antes de sumar.
        Index("ix_transactions_user_currency_occurred", "user_id", "currency", "occurred_on"),
        _OPCIONES_MYSQL,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    type: Mapped[TransactionType] = mapped_column(
        _enum(TransactionType, "transaction_type"), nullable=False
    )
    amount: Mapped[Decimal] = _columna_monto()
    currency: Mapped[str] = _columna_moneda()
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("''"))
    recurring_rule_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("recurring_rules.id", ondelete="SET NULL"), nullable=True
    )


class RecurringOccurrenceModel(Base):
    """Libro mayor de idempotencia del job de recurrentes.

    La UNIQUE `(rule_id, occurred_on)` es la garantía dura: aunque el código
    tenga un bug o dos ejecuciones se pisen, la base impide el duplicado.
    """

    __tablename__ = "recurring_occurrences"
    __table_args__ = (
        UniqueConstraint("rule_id", "occurred_on", name="uq_recurring_occurrences_rule_date"),
        _OPCIONES_MYSQL,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("recurring_rules.id", ondelete="CASCADE"), nullable=False
    )
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[OccurrenceStatus] = mapped_column(
        _enum(OccurrenceStatus, "occurrence_status"), nullable=False
    )
    transaction_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Presupuestos
# ---------------------------------------------------------------------------
class BudgetModel(TimestampMixin, Base):
    """Tope mensual de gasto por categoría y moneda.

    La moneda entra en la UNIQUE: cuando se habilite USD, $200.000 en
    Alimentación y US$100 en la misma categoría son dos presupuestos válidos.
    """

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "category_id", "period_month", "currency", name="uq_budgets_periodo"
        ),
        Index("ix_budgets_user_period", "user_id", "period_month"),
        _OPCIONES_MYSQL,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = _columna_monto()
    currency: Mapped[str] = _columna_moneda()


# ---------------------------------------------------------------------------
# Asistente conversacional
# ---------------------------------------------------------------------------
class ChatMessageModel(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_user_conv", "user_id", "conversation_id", "created_at"),
        _OPCIONES_MYSQL,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    role: Mapped[ChatRole] = mapped_column(_enum(ChatRole, "chat_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class ChatUsageModel(Base):
    """Telemetría de consumo del asistente.

    Se persiste desde la primera consulta para poder recalibrar modelo y
    límites con datos reales en vez de con estimaciones (docs/PROMPT.md §11).
    """

    __tablename__ = "chat_usage"
    __table_args__ = (
        Index("ix_chat_usage_user_created", "user_id", "created_at"),
        _OPCIONES_MYSQL,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Alertas de presupuesto
# ---------------------------------------------------------------------------
class BudgetAlertModel(TimestampMixin, Base):
    """Desvío presupuestario detectado por el job.

    La UNIQUE `(user_id, category_id, period_month, type)` es la garantía de
    idempotencia: sin ella, el job emitiría la misma alerta todos los días
    (docs/PROMPT.md §21.2).
    """

    __tablename__ = "budget_alerts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "category_id",
            "period_month",
            "type",
            name="uq_budget_alerts_user_category_period_type",
        ),
        Index("ix_budget_alerts_user_status", "user_id", "status"),
        _OPCIONES_MYSQL,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[AlertType] = mapped_column(_enum(AlertType, "alert_type"), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(_enum(AlertStatus, "alert_status"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Nullable: la redacta el agente, y si el proveedor no responde la alerta
    # se emite igual.
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    projected_percentage: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)


# ---------------------------------------------------------------------------
# Lectura de tickets
# ---------------------------------------------------------------------------
class ReceiptScanModel(Base):
    """Resultado de una lectura de ticket.

    **No guarda la imagen.** La foto se procesa en memoria y se descarta: puede
    traer los últimos dígitos de una tarjeta o una dirección, y el producto no
    la necesita una vez extraídos los campos (docs/PROMPT.md §21.1). Lo que se
    persiste es qué leyó el modelo y cuánto costó, para poder medir si vale la
    pena y con qué frecuencia se equivoca.
    """

    __tablename__ = "receipt_scans"
    __table_args__ = (
        Index("ix_receipt_scans_user_created", "user_id", "created_at"),
        _OPCIONES_MYSQL,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ReceiptScanStatus] = mapped_column(
        _enum(ReceiptScanStatus, "receipt_scan_status"), nullable=False
    )
    # Todo nullable: un ticket arrugado puede no tener monto legible, y guardar
    # la lectura parcial sirve para saber qué tan seguido pasa.
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    occurred_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    merchant: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    # Confianza por campo, como JSON. Es un dato de diagnóstico y no se
    # consulta por sus claves, así que no justifica columnas propias.
    confidence: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)
    transaction_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Metas de ahorro
# ---------------------------------------------------------------------------
class SavingsGoalModel(TimestampMixin, Base):
    """Objetivo de ahorro con su fecha de inicio.

    No hay tabla de aportes: el producto no maneja cuentas, y el avance se
    calcula contra el balance acumulado desde `starts_on` (docs/PROMPT.md
    §21.3). Guardar aportes sueltos duplicaría movimientos que ya existen.

    `is_active` entra en el índice porque la consulta que importa —el avance
    de la pantalla— pide solo las activas.
    """

    __tablename__ = "savings_goals"
    __table_args__ = (
        Index("ix_savings_goals_user_active", "user_id", "is_active"),
        _OPCIONES_MYSQL,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_amount: Mapped[Decimal] = _columna_monto()
    currency: Mapped[str] = _columna_moneda()
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    # Nullable: hay metas sin fecha, y sin fecha no existe llegar tarde.
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))


__all__ = [
    "BudgetAlertModel",
    "BudgetModel",
    "CategoryModel",
    "ChatMessageModel",
    "ChatUsageModel",
    "ReceiptScanModel",
    "RecurringOccurrenceModel",
    "RecurringRuleModel",
    "RefreshTokenModel",
    "SavingsGoalModel",
    "TransactionModel",
    "UserModel",
]
