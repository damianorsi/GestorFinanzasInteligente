"""DTOs de categorías."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CategoryUsage:
    """Cuántos recursos dependen de una categoría.

    Se cuenta antes de borrar para poder decir exactamente qué está bloqueando
    la operación, en vez de un 409 genérico que obligue a adivinar.
    """

    transactions: int
    budgets: int
    recurring_rules: int

    @property
    def esta_en_uso(self) -> bool:
        return bool(self.transactions or self.budgets or self.recurring_rules)

    def describir(self) -> str:
        """Enumera en español lo que está usando la categoría.

        Ejemplo: "12 movimientos, 1 presupuesto y 2 reglas recurrentes".
        """
        partes = [
            _pluralizar(self.transactions, "movimiento", "movimientos"),
            _pluralizar(self.budgets, "presupuesto", "presupuestos"),
            _pluralizar(self.recurring_rules, "regla recurrente", "reglas recurrentes"),
        ]
        presentes = [parte for parte in partes if parte is not None]
        if len(presentes) <= 1:
            return presentes[0] if presentes else ""
        return f"{', '.join(presentes[:-1])} y {presentes[-1]}"


def _pluralizar(cantidad: int, singular: str, plural: str) -> str | None:
    if cantidad == 0:
        return None
    return f"{cantidad} {singular if cantidad == 1 else plural}"
