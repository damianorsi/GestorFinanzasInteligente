"""Caso de uso: exportar movimientos."""

from __future__ import annotations

import logging

from app.application.dtos import TransactionExportRow, TransactionFilters
from app.application.exceptions import ExportTooLargeError
from app.application.ports import CategoryRepository, TransactionRepository

logger = logging.getLogger(__name__)

CATEGORIA_DESCONOCIDA = "(sin categoría)"


class ExportTransactions:
    """Arma las filas del export respetando los mismos filtros que el listado.

    No incluye proyecciones futuras porque no existen: los movimientos de
    reglas recurrentes solo se materializan hasta el día de hoy
    (docs/PROMPT.md §9).
    """

    def __init__(
        self,
        transactions: TransactionRepository,
        categories: CategoryRepository,
        max_rows: int,
    ) -> None:
        self._transactions = transactions
        self._categories = categories
        self._max_rows = max_rows

    async def execute(
        self, user_id: int, filters: TransactionFilters
    ) -> list[TransactionExportRow]:
        # Se pide uno más del máximo para distinguir "justo el máximo" de "se
        # pasó", y avisar en vez de entregar un archivo truncado en silencio.
        movimientos = await self._transactions.list_for_export(user_id, filters, self._max_rows + 1)
        if len(movimientos) > self._max_rows:
            raise ExportTooLargeError(
                f"La exportación supera las {self._max_rows} filas. "
                "Acotá el rango de fechas o agregá filtros."
            )

        # Una sola consulta de categorías en vez de un JOIN por fila: son pocas
        # y acotadas por usuario.
        nombres = {
            categoria.id: categoria.name
            for categoria in await self._categories.list_for_user(user_id)
        }

        logger.info("Exportación generada", extra={"user_id": user_id, "filas": len(movimientos)})
        return [
            TransactionExportRow(
                id=movimiento.id or 0,
                occurred_on=movimiento.occurred_on,
                type=movimiento.type,
                category_name=nombres.get(movimiento.category_id, CATEGORIA_DESCONOCIDA),
                description=movimiento.description,
                amount=movimiento.money.amount,
                currency=movimiento.money.currency,
                is_recurring=movimiento.is_recurring,
            )
            for movimiento in movimientos
        ]
