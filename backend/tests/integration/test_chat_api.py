"""Tests de extremo a extremo del asistente, con el modelo mockeado.

Se sustituye el puerto `ChatAgent` por un doble: lo que se prueba acá es el
endpoint —cupo, persistencia, telemetría, aislamiento entre usuarios— y no la
redacción del modelo (docs/PROMPT.md §14).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_assistant_agent
from app.application.dtos import AssistantAnswer, ChatMessage, TemporalContext, TokenUsage
from app.application.exceptions import AssistantUnavailableError
from app.application.use_cases.chat.ask_assistant import MENSAJE_DE_FALLBACK
from app.infrastructure.db.models import ChatMessageModel, ChatUsageModel
from app.main import app
from tests.helpers import CuentaDePrueba, crear_cuenta

pytestmark = pytest.mark.integration

RUTA = "/api/v1/chat"
HISTORIAL = "/api/v1/chat/history"


class AgenteDoble:
    """Contesta un texto fijo y anota con qué `user_id` lo llamaron."""

    def __init__(self) -> None:
        self.respuesta = "Gastaste 150000.00 ARS este mes."
        self.error: Exception | None = None
        self.usuarios: list[int] = []
        self.mensajes: list[str] = []
        self.historiales: list[list[ChatMessage]] = []
        self.usage = TokenUsage(
            model="gpt-5-mini",
            prompt_tokens=430,
            completion_tokens=62,
            total_tokens=492,
            tool_calls_count=2,
        )

    async def answer(
        self,
        user_id: int,
        message: str,
        history: Sequence[ChatMessage],
        temporal: TemporalContext,
    ) -> AssistantAnswer:
        self.usuarios.append(user_id)
        self.mensajes.append(message)
        self.historiales.append(list(history))
        if self.error is not None:
            raise self.error
        return AssistantAnswer(content=self.respuesta, usage=self.usage)


@pytest.fixture(autouse=True)
def _base_limpia(db_session: AsyncSession) -> None:
    return None


@pytest.fixture
async def agente() -> AsyncIterator[AgenteDoble]:
    """Reemplaza el agente real mientras dure el test.

    Sin esto la suite llamaría a OpenAI: además de costar plata, ataría los
    tests a la red y a la redacción del modelo, que no es determinista.
    """
    doble = AgenteDoble()
    app.dependency_overrides[get_assistant_agent] = lambda: doble
    yield doble
    app.dependency_overrides.pop(get_assistant_agent, None)


@pytest.fixture
async def cuenta(client: AsyncClient) -> CuentaDePrueba:
    return await crear_cuenta(client, "damian@ejemplo.com")


@pytest.fixture
async def otra_cuenta(client: AsyncClient) -> CuentaDePrueba:
    return await crear_cuenta(client, "otra@ejemplo.com")


class TestConsulta:
    async def test_responde_y_abre_una_conversacion(
        self, client: AsyncClient, cuenta: CuentaDePrueba, agente: AgenteDoble
    ) -> None:
        # Act
        respuesta = await client.post(
            RUTA, headers=cuenta.headers, json={"message": "¿cuánto gasté este mes?"}
        )

        # Assert
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["content"] == "Gastaste 150000.00 ARS este mes."
        assert cuerpo["degraded"] is False
        assert cuerpo["conversation_id"]

    async def test_el_user_id_sale_del_token_y_no_del_body(
        self, client: AsyncClient, cuenta: CuentaDePrueba, agente: AgenteDoble
    ) -> None:
        # Act
        await client.post(RUTA, headers=cuenta.headers, json={"message": "hola"})

        # Assert
        assert agente.usuarios == [cuenta.user_id]

    async def test_rechaza_un_body_con_campos_de_mas(
        self, client: AsyncClient, cuenta: CuentaDePrueba, agente: AgenteDoble
    ) -> None:
        # Act: intentar pasar el usuario por el body no es un camino válido.
        respuesta = await client.post(
            RUTA, headers=cuenta.headers, json={"message": "hola", "user_id": 999}
        )

        # Assert
        assert respuesta.status_code == 422

    async def test_sin_token_responde_401(self, client: AsyncClient, agente: AgenteDoble) -> None:
        # Act
        respuesta = await client.post(RUTA, json={"message": "hola"})

        # Assert
        assert respuesta.status_code == 401

    @pytest.mark.parametrize("mensaje", ["", " " * 3 + "\t", "x" * 1001])
    async def test_valida_el_largo_del_mensaje(
        self, client: AsyncClient, cuenta: CuentaDePrueba, agente: AgenteDoble, mensaje: str
    ) -> None:
        # Act
        respuesta = await client.post(RUTA, headers=cuenta.headers, json={"message": mensaje})

        # Assert
        assert respuesta.status_code == 422, respuesta.text

    async def test_continua_una_conversacion_existente(
        self, client: AsyncClient, cuenta: CuentaDePrueba, agente: AgenteDoble
    ) -> None:
        # Arrange
        primera = await client.post(RUTA, headers=cuenta.headers, json={"message": "¿cuánto?"})
        conversacion = primera.json()["conversation_id"]

        # Act
        segunda = await client.post(
            RUTA,
            headers=cuenta.headers,
            json={"message": "¿y el mes pasado?", "conversation_id": conversacion},
        )

        # Assert
        assert segunda.json()["conversation_id"] == conversacion
        assert [m.content for m in agente.historiales[-1]] == [
            "¿cuánto?",
            "Gastaste 150000.00 ARS este mes.",
        ]


class TestPersistencia:
    async def test_guarda_la_pregunta_y_la_respuesta(
        self,
        client: AsyncClient,
        cuenta: CuentaDePrueba,
        agente: AgenteDoble,
        db_session: AsyncSession,
    ) -> None:
        # Act
        respuesta = await client.post(RUTA, headers=cuenta.headers, json={"message": "¿cuánto?"})
        conversacion = respuesta.json()["conversation_id"]

        # Assert
        filas = (
            await db_session.scalars(
                select(ChatMessageModel)
                .where(ChatMessageModel.conversation_id == conversacion)
                .order_by(ChatMessageModel.id)
            )
        ).all()
        assert [(f.user_id, f.role.value, f.content) for f in filas] == [
            (cuenta.user_id, "USER", "¿cuánto?"),
            (cuenta.user_id, "ASSISTANT", "Gastaste 150000.00 ARS este mes."),
        ]

    async def test_persiste_el_consumo_de_tokens(
        self,
        client: AsyncClient,
        cuenta: CuentaDePrueba,
        agente: AgenteDoble,
        db_session: AsyncSession,
    ) -> None:
        # Act
        respuesta = await client.post(RUTA, headers=cuenta.headers, json={"message": "¿cuánto?"})
        conversacion = respuesta.json()["conversation_id"]

        # Assert: es la única fuente para recalibrar modelo y cupo con datos
        # reales en vez de estimaciones (docs/PROMPT.md §11).
        fila = (
            await db_session.scalars(
                select(ChatUsageModel).where(ChatUsageModel.conversation_id == conversacion)
            )
        ).one()
        assert fila.user_id == cuenta.user_id
        assert fila.model == "gpt-5-mini"
        assert (fila.prompt_tokens, fila.completion_tokens, fila.total_tokens) == (430, 62, 492)
        assert fila.tool_calls_count == 2
        assert fila.latency_ms >= 0


class TestHistorial:
    async def test_devuelve_los_mensajes_en_orden_cronologico(
        self, client: AsyncClient, cuenta: CuentaDePrueba, agente: AgenteDoble
    ) -> None:
        # Arrange
        primera = await client.post(RUTA, headers=cuenta.headers, json={"message": "primera"})
        conversacion = primera.json()["conversation_id"]
        await client.post(
            RUTA,
            headers=cuenta.headers,
            json={"message": "segunda", "conversation_id": conversacion},
        )

        # Act
        respuesta = await client.get(
            HISTORIAL, headers=cuenta.headers, params={"conversation_id": conversacion}
        )

        # Assert
        assert respuesta.status_code == 200, respuesta.text
        assert [(m["role"], m["content"]) for m in respuesta.json()] == [
            ("USER", "primera"),
            ("ASSISTANT", "Gastaste 150000.00 ARS este mes."),
            ("USER", "segunda"),
            ("ASSISTANT", "Gastaste 150000.00 ARS este mes."),
        ]

    async def test_no_devuelve_la_conversacion_de_otro_usuario(
        self,
        client: AsyncClient,
        cuenta: CuentaDePrueba,
        otra_cuenta: CuentaDePrueba,
        agente: AgenteDoble,
    ) -> None:
        # Arrange
        primera = await client.post(RUTA, headers=cuenta.headers, json={"message": "mi secreto"})
        conversacion = primera.json()["conversation_id"]

        # Act: el identificador de conversación no alcanza para leerla.
        respuesta = await client.get(
            HISTORIAL, headers=otra_cuenta.headers, params={"conversation_id": conversacion}
        )

        # Assert
        assert respuesta.status_code == 200
        assert respuesta.json() == []

    async def test_dos_usuarios_no_se_pisan_con_el_mismo_identificador(
        self,
        client: AsyncClient,
        cuenta: CuentaDePrueba,
        otra_cuenta: CuentaDePrueba,
        agente: AgenteDoble,
    ) -> None:
        # Arrange
        await client.post(
            RUTA, headers=cuenta.headers, json={"message": "soy uno", "conversation_id": "misma"}
        )
        await client.post(
            RUTA,
            headers=otra_cuenta.headers,
            json={"message": "soy dos", "conversation_id": "misma"},
        )

        # Act
        respuesta = await client.get(
            HISTORIAL, headers=cuenta.headers, params={"conversation_id": "misma"}
        )

        # Assert
        assert [m["content"] for m in respuesta.json() if m["role"] == "USER"] == ["soy uno"]

    async def test_el_agente_no_recibe_el_historial_ajeno(
        self,
        client: AsyncClient,
        cuenta: CuentaDePrueba,
        otra_cuenta: CuentaDePrueba,
        agente: AgenteDoble,
    ) -> None:
        # Arrange
        await client.post(
            RUTA, headers=cuenta.headers, json={"message": "soy uno", "conversation_id": "misma"}
        )

        # Act
        await client.post(
            RUTA,
            headers=otra_cuenta.headers,
            json={"message": "soy dos", "conversation_id": "misma"},
        )

        # Assert: ni siquiera como contexto del prompt.
        assert agente.historiales[-1] == []


class TestCupo:
    async def test_al_superar_el_limite_responde_429(
        self,
        client: AsyncClient,
        cuenta: CuentaDePrueba,
        agente: AgenteDoble,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange
        _fijar_cupo(monkeypatch, 2)
        for _ in range(2):
            assert (
                await client.post(RUTA, headers=cuenta.headers, json={"message": "hola"})
            ).status_code == 200

        # Act
        respuesta = await client.post(RUTA, headers=cuenta.headers, json={"message": "una más"})

        # Assert
        assert respuesta.status_code == 429
        assert respuesta.json()["code"] == "rate_limit_exceeded"

    async def test_el_cupo_de_uno_no_afecta_al_otro(
        self,
        client: AsyncClient,
        cuenta: CuentaDePrueba,
        otra_cuenta: CuentaDePrueba,
        agente: AgenteDoble,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange
        _fijar_cupo(monkeypatch, 1)
        await client.post(RUTA, headers=cuenta.headers, json={"message": "hola"})

        # Act
        respuesta = await client.post(RUTA, headers=otra_cuenta.headers, json={"message": "hola"})

        # Assert
        assert respuesta.status_code == 200


class TestDegradado:
    async def test_una_caida_del_proveedor_no_devuelve_500(
        self, client: AsyncClient, cuenta: CuentaDePrueba, agente: AgenteDoble
    ) -> None:
        # Arrange
        agente.error = AssistantUnavailableError("OpenAI no responde")

        # Act
        respuesta = await client.post(RUTA, headers=cuenta.headers, json={"message": "¿cuánto?"})

        # Assert
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["content"] == MENSAJE_DE_FALLBACK
        assert cuerpo["degraded"] is True

    async def test_la_respuesta_degradada_igual_queda_registrada(
        self,
        client: AsyncClient,
        cuenta: CuentaDePrueba,
        agente: AgenteDoble,
        db_session: AsyncSession,
    ) -> None:
        # Arrange
        agente.error = AssistantUnavailableError("OpenAI no responde")

        # Act
        respuesta = await client.post(RUTA, headers=cuenta.headers, json={"message": "¿cuánto?"})
        conversacion = respuesta.json()["conversation_id"]

        # Assert
        fila = (
            await db_session.scalars(
                select(ChatUsageModel).where(ChatUsageModel.conversation_id == conversacion)
            )
        ).one()
        assert fila.total_tokens == 0


def _fijar_cupo(monkeypatch: pytest.MonkeyPatch, consultas_por_hora: int) -> None:
    """Baja el cupo por hora sin tener que mandar veinte requests."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "chat_rate_limit_per_hour", consultas_por_hora)
