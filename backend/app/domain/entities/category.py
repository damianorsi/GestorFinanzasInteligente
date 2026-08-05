"""Entidad `Category`."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.enums import TransactionType
from app.domain.exceptions import InvalidCategoryError

LARGO_MAXIMO_NOMBRE = 60
_COLOR_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(slots=True)
class Category:
    """Categoría con la que se clasifican los movimientos.

    No lleva moneda: "Alimentación" sirve para gastos en cualquier moneda
    (docs/PROMPT.md §6).
    """

    user_id: int
    name: str
    type: TransactionType
    id: int | None = None
    color: str | None = None
    is_default: bool = False

    def __post_init__(self) -> None:
        nombre = self.name.strip()
        if not nombre:
            raise InvalidCategoryError("El nombre de la categoría no puede estar vacío.")
        if len(nombre) > LARGO_MAXIMO_NOMBRE:
            raise InvalidCategoryError(
                f"El nombre no puede superar los {LARGO_MAXIMO_NOMBRE} caracteres."
            )
        self.name = nombre

        if self.color is not None:
            color = self.color.strip()
            if not _COLOR_HEX.match(color):
                raise InvalidCategoryError(
                    f"Color inválido: {self.color!r}. Se espera hexadecimal tipo '#1c9e6f'."
                )
            self.color = color.lower()

    @property
    def is_expense(self) -> bool:
        return self.type is TransactionType.EXPENSE
