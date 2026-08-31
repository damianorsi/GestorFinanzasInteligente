"""Puerto de persistencia de las lecturas de ticket."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.application.dtos import ExtractedReceipt


class ReceiptScanRepository(Protocol):
    """Guarda el resultado de cada lectura, **nunca la imagen**.

    La foto se procesa en memoria y se descarta: puede traer los últimos
    dígitos de una tarjeta o una dirección, y el producto no la necesita una
    vez extraídos los campos (docs/PROMPT.md §21.1). Lo que sí se guarda es qué
    leyó el modelo y cuánto costó, para poder medir si vale la pena.
    """

    async def save(
        self,
        user_id: int,
        extracted: ExtractedReceipt,
        category_id: int | None,
        model: str,
        total_tokens: int,
        latency_ms: int,
    ) -> int:
        """Persiste una lectura exitosa y devuelve su id."""
        ...

    async def save_failure(self, user_id: int, model: str, latency_ms: int) -> None:
        """Registra un intento fallido, **aunque el request termine en error**.

        Va en su propia transacción a propósito. El caso de uso vuelve a lanzar
        la excepción, y eso hace que la transacción del request se revierta: si
        esta fila viajara ahí, se perdería con el rollback y un archivo
        ilegible permitiría reintentar sin techo contra un proveedor que cobra
        por llamada.
        """
        ...

    async def count_since(self, user_id: int, since: datetime) -> int:
        """Lecturas del usuario desde ese momento, para el cupo por hora."""
        ...

    async def find_possible_duplicates(
        self, user_id: int, amount: Decimal, occurred_on: date, currency: str
    ) -> list[int]:
        """Movimientos del mismo monto y fecha que ya existen."""
        ...
