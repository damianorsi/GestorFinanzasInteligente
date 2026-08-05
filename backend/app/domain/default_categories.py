"""Categorías que recibe toda cuenta nueva.

Es una regla de negocio y no un dato de configuración: define con qué arranca
una persona usuaria el primer día. Vive en el dominio para que el caso de uso
de registro no tenga que conocer la lista.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities import Category
from app.domain.enums import TransactionType


@dataclass(frozen=True, slots=True)
class CategoriaPorDefecto:
    name: str
    type: TransactionType
    color: str


CATEGORIAS_POR_DEFECTO: tuple[CategoriaPorDefecto, ...] = (
    # Ingresos
    CategoriaPorDefecto("Sueldo", TransactionType.INCOME, "#1c9e6f"),
    CategoriaPorDefecto("Freelance", TransactionType.INCOME, "#2c8a7a"),
    CategoriaPorDefecto("Otros ingresos", TransactionType.INCOME, "#4a9d8f"),
    # Gastos
    CategoriaPorDefecto("Alimentación", TransactionType.EXPENSE, "#d1603d"),
    CategoriaPorDefecto("Transporte", TransactionType.EXPENSE, "#b8532f"),
    CategoriaPorDefecto("Vivienda", TransactionType.EXPENSE, "#8c5b3f"),
    CategoriaPorDefecto("Salud", TransactionType.EXPENSE, "#c0455c"),
    CategoriaPorDefecto("Ocio", TransactionType.EXPENSE, "#7a5ba6"),
    CategoriaPorDefecto("Servicios", TransactionType.EXPENSE, "#3f6fa6"),
    CategoriaPorDefecto("Otros gastos", TransactionType.EXPENSE, "#6b7280"),
)


def construir_categorias_por_defecto(user_id: int) -> list[Category]:
    """Instancia las categorías iniciales para un usuario recién creado."""
    return [
        Category(
            user_id=user_id,
            name=plantilla.name,
            type=plantilla.type,
            color=plantilla.color,
            is_default=True,
        )
        for plantilla in CATEGORIAS_POR_DEFECTO
    ]
