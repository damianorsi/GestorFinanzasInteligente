"""Enumeraciones del dominio.

Son `StrEnum` para que el valor persistido y el serializado en JSON sean el
mismo string, sin tablas de traducción intermedias.
"""

from __future__ import annotations

from enum import StrEnum


class TransactionType(StrEnum):
    """Naturaleza de un movimiento.

    El monto siempre es positivo; el signo lo determina este tipo.
    """

    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class RecurrenceFrequency(StrEnum):
    """Periodicidad de una regla recurrente."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class OccurrenceStatus(StrEnum):
    """Estado de una ocurrencia en el libro mayor de recurrencias.

    `SKIPPED` existe para que el job no vuelva a crear un movimiento que la
    persona usuaria borró a propósito.
    """

    GENERATED = "GENERATED"
    SKIPPED = "SKIPPED"


class BudgetStatus(StrEnum):
    """Cómo viene un presupuesto respecto de su tope."""

    OK = "OK"
    WARNING = "WARNING"
    EXCEEDED = "EXCEEDED"


class AlertType(StrEnum):
    """Qué desvío detectó el job (docs/PROMPT.md §21.2)."""

    # Ya se pasó del tope.
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    # El ritmo proyecta pasarse antes de fin de mes. Es la que hace proactiva
    # la feature: todavía se puede corregir.
    BUDGET_AT_RISK = "BUDGET_AT_RISK"
    # Categoría con gasto relevante y sin tope definido.
    UNBUDGETED_SPENDING = "UNBUDGETED_SPENDING"


class AlertStatus(StrEnum):
    """En qué estado está una alerta.

    `RESOLVED` no se borra: si se borrara, el job la volvería a emitir a la
    corrida siguiente.
    """

    OPEN = "OPEN"
    READ = "READ"
    RESOLVED = "RESOLVED"


class ReceiptScanStatus(StrEnum):
    """En qué terminó la lectura de un ticket.

    `CONFIRMED` no lo pone el lector sino la confirmación posterior: el
    borrador solo se vuelve movimiento cuando la persona lo acepta
    (docs/PROMPT.md §21.1).
    """

    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"
    CONFIRMED = "CONFIRMED"


class ChatRole(StrEnum):
    """Quién emitió un mensaje de la conversación con el asistente."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"


__all__ = [
    "AlertStatus",
    "AlertType",
    "BudgetStatus",
    "ChatRole",
    "OccurrenceStatus",
    "ReceiptScanStatus",
    "RecurrenceFrequency",
    "TransactionType",
]
