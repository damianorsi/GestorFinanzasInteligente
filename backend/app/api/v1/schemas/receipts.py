"""Schemas de la lectura de tickets."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.application.dtos import ReceiptDraft


class ReceiptDraftResponse(BaseModel):
    """Borrador para precargar el formulario de alta.

    **No es un movimiento y no se creó nada.** La confirmación pasa por
    `POST /transactions`, con las mismas validaciones de siempre
    (docs/PROMPT.md §21.1).
    """

    scan_id: int
    amount: str | None
    occurred_on: date
    merchant: str | None
    currency: str
    category_id: int | None
    category_name: str | None
    # Confianza de 0 a 1 por campo leído.
    confidence: dict[str, float]
    # Campos cuya confianza quedó por debajo del umbral. La interfaz los marca
    # para que se revisen antes de confirmar.
    low_confidence_fields: list[str]
    # Movimientos del mismo monto y fecha que ya existen. No bloquea el alta.
    possible_duplicates: list[int]

    @classmethod
    def desde(cls, borrador: ReceiptDraft) -> ReceiptDraftResponse:
        return cls(
            scan_id=borrador.scan_id,
            amount=None if borrador.amount is None else str(borrador.amount),
            occurred_on=borrador.occurred_on,
            merchant=borrador.merchant,
            currency=borrador.currency,
            category_id=borrador.category_id,
            category_name=borrador.category_name,
            confidence=borrador.confidence,
            low_confidence_fields=borrador.campos_dudosos,
            possible_duplicates=borrador.possible_duplicates,
        )
