"""Paginación offset-based."""

from __future__ import annotations

from dataclasses import dataclass

LIMITE_POR_DEFECTO = 20
LIMITE_MAXIMO = 100


@dataclass(frozen=True, slots=True)
class Page:
    """Ventana pedida por el cliente."""

    offset: int = 0
    limit: int = LIMITE_POR_DEFECTO

    def __post_init__(self) -> None:
        if self.offset < 0:
            raise ValueError("El offset no puede ser negativo.")
        if not 1 <= self.limit <= LIMITE_MAXIMO:
            raise ValueError(f"El limit debe estar entre 1 y {LIMITE_MAXIMO}.")


@dataclass(frozen=True, slots=True)
class PaginatedResult[T]:
    """Una página de resultados junto al total que cumple el filtro.

    `total_count` cuenta los que matchean el filtro, no los devueltos: sin eso
    el frontend no puede dibujar el paginador.
    """

    entries: list[T]
    offset: int
    limit: int
    total_count: int
