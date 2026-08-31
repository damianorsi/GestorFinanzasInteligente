"""Puerto del lector de tickets."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.application.dtos import ExtractedReceipt
from app.domain.entities import Category


class ReceiptReader(Protocol):
    """Extrae los datos de la foto de un ticket.

    Recibe las categorías del usuario y **el modelo elige entre ésas**: no
    inventa una. Es el mismo principio que las tools del asistente —el modelo
    decide dentro de un conjunto acotado— y evita que el borrador proponga una
    categoría que no existe (docs/PROMPT.md §21.1).
    """

    async def read(
        self, image: bytes, mime_type: str, categories: Sequence[Category]
    ) -> ExtractedReceipt:
        """Devuelve lo leído, con la confianza de cada campo.

        Lanza `ReceiptUnreadableError` si la imagen no es un ticket legible, y
        `AssistantUnavailableError` si el proveedor falla o se agota el tiempo.
        Nunca devuelve un borrador inventado con ceros: un monto en cero que
        parece leído es peor que un error explícito.
        """
        ...
