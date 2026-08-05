"""Puerto del libro mayor de ocurrencias recurrentes.

Se necesita ya en la fase de movimientos, aunque el job que las genera llegue
después: borrar un movimiento generado por una regla tiene que marcar su
ocurrencia como salteada. Si no, el job la volvería a crear y el movimiento
que la persona usuaria borró a propósito reaparecería.
"""

from __future__ import annotations

from typing import Protocol


class RecurringOccurrenceRepository(Protocol):
    async def mark_skipped_by_transaction(self, transaction_id: int) -> None:
        """Marca como SKIPPED la ocurrencia de un movimiento que se borra.

        No borra la fila: si la borrara, el job volvería a generar el
        movimiento en la siguiente corrida. Es idempotente y no falla si el
        movimiento no vino de una regla.
        """
        ...
