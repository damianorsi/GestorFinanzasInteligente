"""Puerto del agente conversacional."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.application.dtos import AssistantAnswer, ChatMessage, TemporalContext


class ChatAgent(Protocol):
    """Responde una consulta en lenguaje natural sobre las finanzas del usuario.

    El `user_id` es un parámetro de esta llamada y **nunca** algo que el modelo
    pueda elegir: la implementación construye las herramientas con ese id ya
    cerrado, de modo que una prompt injection no tiene forma de pedir los datos
    de otra persona (docs/PROMPT.md §11).
    """

    async def answer(
        self,
        user_id: int,
        message: str,
        history: Sequence[ChatMessage],
        temporal: TemporalContext,
    ) -> AssistantAnswer:
        """Devuelve la respuesta junto al consumo de tokens.

        Lanza `AssistantUnavailableError` si el proveedor falla o se agota el
        tiempo; nunca propaga excepciones del SDK hacia arriba.
        """
        ...
