"""Persistencia del asistente sobre SQLAlchemy."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos import ChatMessage, TokenUsage
from app.domain.enums import ChatRole
from app.infrastructure.clock import a_utc_naive
from app.infrastructure.db.models import ChatMessageModel, ChatUsageModel


class SqlAlchemyChatRepository:
    """Implementación del puerto `ChatRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_message(
        self, user_id: int, conversation_id: str, role: ChatRole, content: str
    ) -> None:
        self._session.add(
            ChatMessageModel(
                user_id=user_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
            )
        )
        await self._session.flush()

    async def history(self, user_id: int, conversation_id: str, limit: int) -> list[ChatMessage]:
        # Se traen los últimos `limit` en orden inverso y se da vuelta después:
        # ordenar ascendente y cortar devolvería los más viejos.
        modelos = (
            await self._session.scalars(
                select(ChatMessageModel)
                .where(
                    ChatMessageModel.user_id == user_id,
                    ChatMessageModel.conversation_id == conversation_id,
                )
                .order_by(ChatMessageModel.created_at.desc(), ChatMessageModel.id.desc())
                .limit(limit)
            )
        ).all()

        return [
            ChatMessage(role=modelo.role, content=modelo.content, created_at=modelo.created_at)
            for modelo in reversed(modelos)
        ]

    async def count_user_messages_since(self, user_id: int, since: datetime) -> int:
        total = await self._session.scalar(
            select(func.count())
            .select_from(ChatMessageModel)
            .where(
                ChatMessageModel.user_id == user_id,
                ChatMessageModel.role == ChatRole.USER,
                ChatMessageModel.created_at >= a_utc_naive(since),
            )
        )
        return int(total or 0)

    async def save_usage(
        self, user_id: int, conversation_id: str, usage: TokenUsage, latency_ms: int
    ) -> None:
        self._session.add(
            ChatUsageModel(
                user_id=user_id,
                conversation_id=conversation_id,
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                tool_calls_count=usage.tool_calls_count,
                latency_ms=latency_ms,
            )
        )
        await self._session.flush()
