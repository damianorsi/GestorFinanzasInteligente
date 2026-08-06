"""Tests del caso de uso del asistente.

El agente va mockeado: acá se prueba la orquestación —cupo, historial,
telemetría, degradado— y no la redacción del modelo (docs/PROMPT.md §14).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

import pytest

from app.application.dtos import AssistantAnswer, ChatMessage, TemporalContext, TokenUsage
from app.application.exceptions import AssistantUnavailableError, RateLimitExceededError
from app.application.use_cases.chat import AskAssistant, GetChatHistory
from app.application.use_cases.chat.ask_assistant import MENSAJE_DE_FALLBACK
from app.domain.enums import ChatRole
from tests.fakes import FakeChatRepository, FixedClock

AHORA = datetime(2026, 8, 5, 12, 0, 0)


class AgenteFalso:
    """Devuelve siempre lo mismo y anota con qué lo llamaron."""

    def __init__(
        self, respuesta: AssistantAnswer | None = None, error: Exception | None = None
    ) -> None:
        self._respuesta = respuesta or AssistantAnswer(
            content="Gastaste 1000 ARS.",
            usage=TokenUsage(
                model="gpt-5-mini",
                prompt_tokens=120,
                completion_tokens=30,
                total_tokens=150,
                tool_calls_count=2,
            ),
        )
        self._error = error
        self.llamadas: list[tuple[int, str, list[ChatMessage], TemporalContext]] = []

    async def answer(
        self,
        user_id: int,
        message: str,
        history: Sequence[ChatMessage],
        temporal: TemporalContext,
    ) -> AssistantAnswer:
        self.llamadas.append((user_id, message, list(history), temporal))
        if self._error is not None:
            raise self._error
        return self._respuesta


def _caso(
    agente: AgenteFalso,
    chat: FakeChatRepository,
    *,
    history_window: int = 6,
    rate_limit: int = 20,
) -> AskAssistant:
    return AskAssistant(
        agent=agente,
        chat=chat,
        clock=FixedClock(AHORA),
        history_window=history_window,
        rate_limit_per_hour=rate_limit,
    )


class TestConversacion:
    async def test_devuelve_la_respuesta_y_abre_una_conversacion_nueva(self) -> None:
        # Arrange
        agente, chat = AgenteFalso(), FakeChatRepository(AHORA)

        # Act
        conversacion, respuesta = await _caso(agente, chat).execute(7, "¿cuánto gasté?")

        # Assert
        assert respuesta.content == "Gastaste 1000 ARS."
        assert respuesta.degraded is False
        assert conversacion  # se generó un identificador

    async def test_respeta_la_conversacion_que_le_pasan(self) -> None:
        # Arrange
        agente, chat = AgenteFalso(), FakeChatRepository(AHORA)

        # Act
        conversacion, _ = await _caso(agente, chat).execute(7, "hola", conversation_id="abc123")

        # Assert
        assert conversacion == "abc123"

    async def test_persiste_la_pregunta_y_la_respuesta(self) -> None:
        # Arrange
        agente, chat = AgenteFalso(), FakeChatRepository(AHORA)

        # Act
        conversacion, _ = await _caso(agente, chat).execute(7, "¿cuánto gasté?")

        # Assert
        guardados = await chat.history(7, conversacion, 10)
        assert [(m.role, m.content) for m in guardados] == [
            (ChatRole.USER, "¿cuánto gasté?"),
            (ChatRole.ASSISTANT, "Gastaste 1000 ARS."),
        ]

    async def test_le_pasa_al_agente_el_historial_previo_sin_repetir_la_consulta(self) -> None:
        # Arrange
        agente, chat = AgenteFalso(), FakeChatRepository(AHORA)
        caso = _caso(agente, chat)
        conversacion, _ = await caso.execute(7, "¿cuánto gasté?")

        # Act
        await caso.execute(7, "¿y el mes pasado?", conversation_id=conversacion)

        # Assert
        _, _, historial, _ = agente.llamadas[-1]
        assert [(m.role, m.content) for m in historial] == [
            (ChatRole.USER, "¿cuánto gasté?"),
            (ChatRole.ASSISTANT, "Gastaste 1000 ARS."),
        ]

    async def test_no_mezcla_el_historial_de_otro_usuario(self) -> None:
        # Arrange
        agente, chat = AgenteFalso(), FakeChatRepository(AHORA)
        caso = _caso(agente, chat)
        await caso.execute(7, "secreto de siete", conversation_id="misma")

        # Act
        await caso.execute(8, "consulta de ocho", conversation_id="misma")

        # Assert
        _, _, historial, _ = agente.llamadas[-1]
        assert historial == []

    async def test_recorta_el_historial_a_la_ventana_configurada(self) -> None:
        # Arrange
        agente, chat = AgenteFalso(), FakeChatRepository(AHORA)
        caso = _caso(agente, chat, history_window=2)
        for numero in range(3):
            await caso.execute(7, f"consulta {numero}", conversation_id="c1")

        # Act
        await caso.execute(7, "última", conversation_id="c1")

        # Assert
        _, _, historial, _ = agente.llamadas[-1]
        assert len(historial) <= 2


class TestContextoTemporal:
    async def test_resuelve_las_fechas_con_el_reloj_y_no_las_deja_al_modelo(self) -> None:
        # Arrange
        agente, chat = AgenteFalso(), FakeChatRepository(AHORA)

        # Act
        await _caso(agente, chat).execute(7, "¿cuánto gasté?")

        # Assert
        _, _, _, temporal = agente.llamadas[-1]
        assert temporal.today == "2026-08-05"
        assert temporal.current_month_from == "2026-08-01"
        assert temporal.current_month_to == "2026-08-31"
        assert temporal.previous_month_from == "2026-07-01"
        assert temporal.previous_month_to == "2026-07-31"


class TestCupo:
    async def test_corta_al_llegar_al_limite_por_hora(self) -> None:
        # Arrange
        agente, chat = AgenteFalso(), FakeChatRepository(AHORA)
        caso = _caso(agente, chat, rate_limit=2)
        await caso.execute(7, "una")
        await caso.execute(7, "dos")

        # Act / Assert
        with pytest.raises(RateLimitExceededError):
            await caso.execute(7, "tres")

    async def test_el_cupo_es_por_usuario(self) -> None:
        # Arrange
        agente, chat = AgenteFalso(), FakeChatRepository(AHORA)
        caso = _caso(agente, chat, rate_limit=1)
        await caso.execute(7, "una")

        # Act
        _, respuesta = await caso.execute(8, "una")

        # Assert
        assert respuesta.degraded is False

    async def test_solo_cuentan_las_consultas_de_la_ultima_hora(self) -> None:
        # Arrange: una consulta de hace dos horas no debería seguir ocupando cupo.
        agente = AgenteFalso()
        chat = FakeChatRepository(AHORA - timedelta(hours=2))
        await chat.save_message(7, "c1", ChatRole.USER, "vieja")
        chat.ahora = AHORA

        # Act
        _, respuesta = await _caso(agente, chat, rate_limit=1).execute(7, "nueva")

        # Assert
        assert respuesta.content == "Gastaste 1000 ARS."

    async def test_una_consulta_que_falla_igual_consume_cupo(self) -> None:
        # Arrange: si el mensaje se guardara recién al final, un usuario podría
        # reintentar sin límite contra un proveedor caído.
        agente = AgenteFalso(error=AssistantUnavailableError("caído"))
        chat = FakeChatRepository(AHORA)
        caso = _caso(agente, chat, rate_limit=1)
        await caso.execute(7, "una")

        # Act / Assert
        with pytest.raises(RateLimitExceededError):
            await caso.execute(7, "dos")


class TestDegradado:
    async def test_devuelve_el_fallback_cuando_el_proveedor_falla(self) -> None:
        # Arrange
        agente = AgenteFalso(error=AssistantUnavailableError("sin OpenAI"))
        chat = FakeChatRepository(AHORA)

        # Act
        _, respuesta = await _caso(agente, chat).execute(7, "¿cuánto gasté?")

        # Assert
        assert respuesta.content == MENSAJE_DE_FALLBACK
        assert respuesta.degraded is True

    async def test_el_fallback_queda_en_el_historial(self) -> None:
        # Arrange
        agente = AgenteFalso(error=AssistantUnavailableError("sin OpenAI"))
        chat = FakeChatRepository(AHORA)

        # Act
        conversacion, _ = await _caso(agente, chat).execute(7, "¿cuánto gasté?")

        # Assert
        guardados = await chat.history(7, conversacion, 10)
        assert guardados[-1].content == MENSAJE_DE_FALLBACK


class TestTelemetria:
    async def test_persiste_el_consumo_de_la_consulta(self) -> None:
        # Arrange
        agente, chat = AgenteFalso(), FakeChatRepository(AHORA)

        # Act
        conversacion, _ = await _caso(agente, chat).execute(7, "¿cuánto gasté?")

        # Assert
        assert len(chat.consumos) == 1
        user_id, conv, uso, latencia = chat.consumos[0]
        assert (user_id, conv) == (7, conversacion)
        assert (uso.model, uso.total_tokens, uso.tool_calls_count) == ("gpt-5-mini", 150, 2)
        assert latencia >= 0

    async def test_tambien_registra_el_consumo_de_una_respuesta_degradada(self) -> None:
        # Arrange
        agente = AgenteFalso(error=AssistantUnavailableError("sin OpenAI"))
        chat = FakeChatRepository(AHORA)

        # Act
        await _caso(agente, chat).execute(7, "¿cuánto gasté?")

        # Assert: la fila existe aunque no haya tokens, para poder medir cuántas
        # consultas se degradaron sin cruzar tablas.
        assert len(chat.consumos) == 1
        assert chat.consumos[0][2].total_tokens == 0


class TestHistorial:
    async def test_devuelve_los_mensajes_de_la_conversacion(self) -> None:
        # Arrange
        chat = FakeChatRepository(AHORA)
        await chat.save_message(7, "c1", ChatRole.USER, "hola")
        await chat.save_message(7, "c1", ChatRole.ASSISTANT, "hola, ¿en qué te ayudo?")
        await chat.save_message(7, "c2", ChatRole.USER, "otra conversación")

        # Act
        mensajes = await GetChatHistory(chat, 6).execute(7, "c1")

        # Assert
        assert [m.content for m in mensajes] == ["hola", "hola, ¿en qué te ayudo?"]

    async def test_no_devuelve_la_conversacion_de_otro_usuario(self) -> None:
        # Arrange
        chat = FakeChatRepository(AHORA)
        await chat.save_message(7, "c1", ChatRole.USER, "secreto de siete")

        # Act
        mensajes = await GetChatHistory(chat, 6).execute(8, "c1")

        # Assert
        assert mensajes == []

    async def test_el_limite_explicito_pisa_la_ventana_por_defecto(self) -> None:
        # Arrange
        chat = FakeChatRepository(AHORA)
        for numero in range(5):
            await chat.save_message(7, "c1", ChatRole.USER, f"mensaje {numero}")

        # Act
        mensajes = await GetChatHistory(chat, 6).execute(7, "c1", limit=2)

        # Assert
        assert [m.content for m in mensajes] == ["mensaje 3", "mensaje 4"]
