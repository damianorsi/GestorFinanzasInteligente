"""Entidad `SavingsGoal`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.exceptions import InvalidSavingsGoalError
from app.domain.value_objects import Money

LARGO_MAXIMO_DEL_NOMBRE = 120


@dataclass(slots=True)
class SavingsGoal:
    """Un objetivo de ahorro con su fecha de inicio.

    No hay una cuenta detrás: el producto no maneja cuentas. El avance se mide
    contra el balance acumulado desde `starts_on` (docs/PROMPT.md §21.3), así
    que la fecha de inicio no es decorativa: define qué movimientos cuentan.

    `target_date` es opcional porque hay metas sin fecha («juntar un colchón»).
    Sin fecha no existe llegar tarde, y el estado se calcula distinto.
    """

    user_id: int
    name: str
    target: Money
    starts_on: date
    target_date: date | None = None
    is_active: bool = True
    id: int | None = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise InvalidSavingsGoalError("La meta necesita un nombre.")
        if len(self.name) > LARGO_MAXIMO_DEL_NOMBRE:
            raise InvalidSavingsGoalError(
                f"El nombre no puede superar los {LARGO_MAXIMO_DEL_NOMBRE} caracteres."
            )
        if not self.target.is_positive:
            raise InvalidSavingsGoalError("El objetivo de la meta tiene que ser mayor a cero.")
        if self.target_date is not None and self.target_date < self.starts_on:
            raise InvalidSavingsGoalError(
                "La fecha objetivo no puede ser anterior al inicio de la meta."
            )
