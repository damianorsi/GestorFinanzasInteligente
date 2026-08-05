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


class ChatRole(StrEnum):
    """Quién emitió un mensaje de la conversación con el asistente."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"


__all__ = [
    "BudgetStatus",
    "ChatRole",
    "OccurrenceStatus",
    "RecurrenceFrequency",
    "TransactionType",
]
