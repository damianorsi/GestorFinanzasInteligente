"""Puerto de persistencia de categorías."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.application.dtos import CategoryUsage
from app.domain.entities import Category
from app.domain.enums import TransactionType


class CategoryRepository(Protocol):
    """Todos los métodos reciben `user_id` y filtran por él.

    No hay un `get_by_id` suelto a propósito: si existiera, alcanzaría con
    olvidarse de comparar el dueño en un solo caso de uso para filtrar datos
    ajenos. Con el `user_id` en la firma, el filtro no se puede omitir.
    """

    async def create_many(self, categories: Sequence[Category]) -> None:
        """Persiste varias categorías de una. Lo usa el seed del registro."""
        ...

    async def create(self, category: Category) -> Category:
        """Persiste una categoría y la devuelve con su `id`."""
        ...

    async def update(self, category: Category) -> Category:
        """Guarda los cambios de una categoría existente."""
        ...

    async def delete(self, user_id: int, category_id: int) -> None: ...

    async def count_for_user(self, user_id: int) -> int: ...

    async def list_for_user(
        self, user_id: int, type: TransactionType | None = None
    ) -> list[Category]:
        """Categorías del usuario, ordenadas por tipo y nombre."""
        ...

    async def get_for_user(self, user_id: int, category_id: int) -> Category | None:
        """La categoría, solo si pertenece a ese usuario."""
        ...

    async def exists_with_name(
        self,
        user_id: int,
        name: str,
        type: TransactionType,
        exclude_id: int | None = None,
    ) -> bool:
        """Si el usuario ya tiene otra categoría con ese nombre y tipo.

        `exclude_id` permite que una edición que no cambia el nombre no choque
        contra sí misma.
        """
        ...

    async def count_usages(self, category_id: int) -> CategoryUsage:
        """Cuántos movimientos, presupuestos y reglas dependen de la categoría."""
        ...
