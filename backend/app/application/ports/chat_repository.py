"""Puerto de persistencia del asistente."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.application.dtos import ChatMessage, TokenUsage
from app.domain.enums import ChatRole


class ChatRepository(Protocol):
    async def save_message(
        self, user_id: int, conversation_id: str, role: ChatRole, content: str
    ) -> None: ...

    async def history(self, user_id: int, conversation_id: str, limit: int) -> list[ChatMessage]:
        """Últimos `limit` mensajes de la conversación, en orden cronológico.

        La ventana es acotada a propósito: reenviar la conversación completa
        hace crecer el consumo de tokens de forma cuadrática a lo largo del
        chat.
        """
        ...

    async def count_user_messages_since(self, user_id: int, since: datetime) -> int:
        """Consultas hechas por el usuario desde un instante dado.

        Es la base del rate limit. Se cuentan los mensajes del usuario y no las
        respuestas ni las filas de consumo, porque el mensaje se persiste antes
        de llamar al modelo: así una tanda de consultas que fallan igual cuenta
        contra el límite y no se puede abusar del error para saltearlo.
        """
        ...

    async def save_usage(
        self, user_id: int, conversation_id: str, usage: TokenUsage, latency_ms: int
    ) -> None: ...
