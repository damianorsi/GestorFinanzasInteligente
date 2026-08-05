"""Puerto de persistencia de categorías.

Por ahora expone solo lo que necesita el registro (sembrar las categorías por
defecto). El resto de los métodos los agrega la fase 4, cuando existan los
casos de uso que definen sus firmas.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.domain.entities import Category


class CategoryRepository(Protocol):
    async def create_many(self, categories: Sequence[Category]) -> None:
        """Persiste varias categorías de una."""
        ...

    async def count_for_user(self, user_id: int) -> int:
        """Cuántas categorías tiene un usuario."""
        ...
