"""Caso de uso: consultar al asistente."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta

from app.application.dtos import (
    AssistantAnswer,
    ChatMessage,
    TemporalContext,
    TokenUsage,
)
from app.application.exceptions import (
    AssistantUnavailableError,
    RateLimitExceededError,
)
from app.application.ports import ChatAgent, ChatRepository, Clock
from app.domain.calendar import (
    etiqueta_de_periodo,
    primer_dia_del_mes,
    sumar_meses,
    ultimo_dia_del_mes,
)
from app.domain.enums import ChatRole

logger = logging.getLogger(__name__)

MENSAJE_DE_FALLBACK = (
    "No pude consultar tus datos en este momento. Probá de nuevo en un ratito; "
    "si sigue fallando, revisá que el asistente esté configurado."
)


class AskAssistant:
    """Orquesta una consulta: cupo, historial, agente y telemetría.

    Deliberadamente no sabe nada de LangChain ni de OpenAI: eso vive detrás del
    puerto `ChatAgent`.
    """

    def __init__(
        self,
        agent: ChatAgent,
        chat: ChatRepository,
        clock: Clock,
        history_window: int,
        rate_limit_per_hour: int,
    ) -> None:
        self._agent = agent
        self._chat = chat
        self._clock = clock
        self._history_window = history_window
        self._rate_limit_per_hour = rate_limit_per_hour

    async def execute(
        self, user_id: int, message: str, conversation_id: str | None = None
    ) -> tuple[str, AssistantAnswer]:
        conversacion = conversation_id or uuid.uuid4().hex
        ahora = self._clock.now()

        consultas = await self._chat.count_user_messages_since(user_id, ahora - timedelta(hours=1))
        if consultas >= self._rate_limit_per_hour:
            raise RateLimitExceededError(
                f"Llegaste al límite de {self._rate_limit_per_hour} consultas por hora. "
                "Probá de nuevo más tarde."
            )

        # Se persiste antes de llamar al modelo: así una consulta que termina
        # fallando igual cuenta contra el cupo y el historial no queda con
        # huecos.
        await self._chat.save_message(user_id, conversacion, ChatRole.USER, message)

        historial = await self._chat.history(user_id, conversacion, self._history_window)
        # El mensaje recién guardado no va en el historial: se pasa aparte como
        # la consulta actual, y duplicarlo haría que el modelo lo lea dos veces.
        previos = [m for m in historial if not (m.role is ChatRole.USER and m.content == message)]

        comenzo = time.perf_counter()
        try:
            respuesta = await self._agent.answer(
                user_id=user_id,
                message=message,
                history=previos,
                temporal=self._contexto_temporal(),
            )
        except AssistantUnavailableError:
            logger.warning("El asistente no estuvo disponible", extra={"user_id": user_id})
            respuesta = AssistantAnswer(
                content=MENSAJE_DE_FALLBACK,
                usage=TokenUsage(model="n/a"),
                degraded=True,
            )

        latencia_ms = int((time.perf_counter() - comenzo) * 1000)

        await self._chat.save_message(user_id, conversacion, ChatRole.ASSISTANT, respuesta.content)
        await self._chat.save_usage(user_id, conversacion, respuesta.usage, latencia_ms)

        logger.info(
            "Consulta al asistente",
            extra={
                "user_id": user_id,
                "conversation_id": conversacion,
                "total_tokens": respuesta.usage.total_tokens,
                "tool_calls": respuesta.usage.tool_calls_count,
                "latency_ms": latencia_ms,
                "degraded": respuesta.degraded,
            },
        )
        return conversacion, respuesta

    def _contexto_temporal(self) -> TemporalContext:
        hoy = self._clock.today()
        mes_anterior = sumar_meses(primer_dia_del_mes(hoy), -1)
        return TemporalContext(
            today=hoy.isoformat(),
            current_month=etiqueta_de_periodo(hoy),
            current_month_from=primer_dia_del_mes(hoy).isoformat(),
            current_month_to=ultimo_dia_del_mes(hoy).isoformat(),
            previous_month=etiqueta_de_periodo(mes_anterior),
            previous_month_from=primer_dia_del_mes(mes_anterior).isoformat(),
            previous_month_to=ultimo_dia_del_mes(mes_anterior).isoformat(),
        )


class GetChatHistory:
    def __init__(self, chat: ChatRepository, history_window: int) -> None:
        self._chat = chat
        self._history_window = history_window

    async def execute(
        self, user_id: int, conversation_id: str, limit: int | None = None
    ) -> list[ChatMessage]:
        return await self._chat.history(user_id, conversation_id, limit or self._history_window)
