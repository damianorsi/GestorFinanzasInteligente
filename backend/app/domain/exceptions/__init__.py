"""Excepciones de negocio.

No heredan de las excepciones HTTP: el dominio no sabe nada de HTTP ni de
FastAPI. La capa de API las traduce a códigos y estados (app/core/errors.py).
"""

from __future__ import annotations


class DomainError(Exception):
    """Raíz de todos los errores de negocio."""


class InvalidMoneyError(DomainError):
    """El monto o la moneda no son representables como dinero."""


class CurrencyMismatchError(DomainError):
    """Se intentó operar entre dos monedas distintas.

    Nunca se convierte de forma implícita: la conversión requiere una fuente de
    cotización y una política de qué tipo de cambio aplicar, que son decisiones
    de producto todavía no tomadas.
    """


class InvalidUserError(DomainError):
    """Los datos del usuario no cumplen las reglas del dominio."""


class InvalidCategoryError(DomainError):
    """Los datos de la categoría no cumplen las reglas del dominio."""


class InvalidTransactionError(DomainError):
    """Los datos del movimiento no cumplen las reglas del dominio."""


class InvalidBudgetError(DomainError):
    """Los datos del presupuesto no cumplen las reglas del dominio."""


class InvalidSavingsGoalError(DomainError):
    """Los datos de la meta de ahorro no cumplen las reglas del dominio."""


class InvalidRecurringRuleError(DomainError):
    """Los datos de la regla recurrente no cumplen las reglas del dominio."""


__all__ = [
    "CurrencyMismatchError",
    "DomainError",
    "InvalidBudgetError",
    "InvalidCategoryError",
    "InvalidMoneyError",
    "InvalidRecurringRuleError",
    "InvalidSavingsGoalError",
    "InvalidTransactionError",
    "InvalidUserError",
]
