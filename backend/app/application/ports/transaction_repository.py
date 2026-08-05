"""Puerto de persistencia de movimientos."""

from __future__ import annotations

from typing import Protocol

from app.application.dtos import Page, PaginatedResult, TransactionFilters
from app.domain.entities import Transaction


class TransactionRepository(Protocol):
    """Igual que el de categorías: `user_id` en todas las firmas.

    No existe un `get_by_id` sin dueño, para que no se pueda escribir por
    accidente una consulta que devuelva movimientos ajenos.
    """

    async def create(self, transaction: Transaction) -> Transaction: ...

    async def update(self, transaction: Transaction) -> Transaction: ...

    async def delete(self, user_id: int, transaction_id: int) -> None: ...

    async def get_for_user(self, user_id: int, transaction_id: int) -> Transaction | None: ...

    async def search(
        self, user_id: int, filters: TransactionFilters, page: Page
    ) -> PaginatedResult[Transaction]:
        """Lista paginada de movimientos que cumplen el filtro."""
        ...

    async def list_for_export(
        self, user_id: int, filters: TransactionFilters, limit: int
    ) -> list[Transaction]:
        """Movimientos sin paginar, para el export.

        `limit` no es opcional: acota cuánto se puede traer a memoria de una.
        El caso de uso pide uno más del máximo para poder distinguir "justo el
        máximo" de "se pasó" y avisar en vez de truncar en silencio.
        """
        ...
