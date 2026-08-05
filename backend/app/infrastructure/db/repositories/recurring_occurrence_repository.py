"""Repositorio del libro mayor de ocurrencias recurrentes."""

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OccurrenceStatus
from app.infrastructure.db.models import RecurringOccurrenceModel


class SqlAlchemyRecurringOccurrenceRepository:
    """Implementación del puerto `RecurringOccurrenceRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def mark_skipped_by_transaction(self, transaction_id: int) -> None:
        # Se marca SKIPPED y NO se borra la fila: borrarla haría que el job
        # volviera a generar el movimiento en la corrida siguiente.
        # `transaction_id = NULL` se pone explícito acá y no se deja al ON
        # DELETE SET NULL de la FK, para no depender del orden en que la base
        # aplique las dos operaciones.
        await self._session.execute(
            update(RecurringOccurrenceModel)
            .where(RecurringOccurrenceModel.transaction_id == transaction_id)
            .values(status=OccurrenceStatus.SKIPPED, transaction_id=None)
        )
