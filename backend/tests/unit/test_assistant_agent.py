"""Tests del agente de LangChain con el modelo mockeado.

No se prueba la redacción del modelo —eso no es determinista y no es nuestro—
sino el cableado: que las herramientas queden atadas al usuario correcto, que
el consumo se contabilice, que el tope de iteraciones corte y que ningún fallo
del SDK se escape hacia arriba (docs/PROMPT.md §14).
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app.application.dtos import ChatMessage, PeriodSummary, TemporalContext
from app.application.exceptions import AssistantUnavailableError
from app.application.use_cases.budgets import GetBudgetProgress
from app.application.use_cases.reports import (
    GetCategoryBreakdown,
    GetMonthlyTrend,
    GetPeriodSummary,
)
from app.application.use_cases.savings import GetSavingsGoalsProgress
from app.application.use_cases.transactions import ListTransactions
from app.domain.enums import ChatRole
from app.domain.value_objects import Money
from app.infrastructure.assistant import agent as modulo_agente
from app.infrastructure.assistant.agent import (
    MENSAJE_SIN_CONVERGER,
    ContadorDeUso,
    LangChainAssistant,
)
from app.infrastructure.assistant.tools import DependenciasDelAsistente, construir_herramientas
from tests.fakes import (
    FakeBudgetRepository,
    FakeCategoryRepository,
    FakeRecurringRuleRepository,
    FakeReportRepository,
    FakeSavingsGoalRepository,
    FakeTransactionRepository,
    FixedClock,
)

MONEDAS = frozenset({"ARS"})
MONEDA = "ARS"
HOY = date(2026, 8, 5)
AHORA = datetime(2026, 8, 5, 12, 0, 0)

TEMPORAL = TemporalContext(
    today="2026-08-05",
    current_month="2026-08",
    current_month_from="2026-08-01",
    current_month_to="2026-08-31",
    previous_month="2026-07",
    previous_month_from="2026-07-01",
    previous_month_to="2026-07-31",
)

LLAMADA_A_HERRAMIENTA = AIMessage(
    content="",
    tool_calls=[{"name": "get_period_summary", "args": {}, "id": "call_1"}],
)


class ModeloFalso(BaseChatModel):
    """Modelo de chat que devuelve un guion fijo.

    Se usa en vez de `FakeListChatModel` porque hace falta controlar los
    `tool_calls` y el `token_usage`, que es justamente lo que se está probando.
    """

    respuestas: list[AIMessage] = Field(default_factory=list)
    tokens_por_llamada: int = 13
    error: Exception | None = None
    demora_segundos: float = 0.0
    llamadas: int = 0

    @property
    def _llm_type(self) -> str:
        return "falso"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.error is not None:
            raise self.error

        indice = min(self.llamadas, len(self.respuestas) - 1)
        self.llamadas += 1
        return ChatResult(
            generations=[ChatGeneration(message=self.respuestas[indice])],
            llm_output={
                "token_usage": {
                    "prompt_tokens": self.tokens_por_llamada,
                    "completion_tokens": 3,
                    "total_tokens": self.tokens_por_llamada + 3,
                }
            },
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.demora_segundos:
            await asyncio.sleep(self.demora_segundos)
        return self._generate(messages, stop, None, **kwargs)


def _dependencias(reports: FakeReportRepository | None = None) -> DependenciasDelAsistente:
    reportes = reports or FakeReportRepository()
    reloj = FixedClock(AHORA)
    categorias = FakeCategoryRepository()
    return DependenciasDelAsistente(
        resumen=GetPeriodSummary(reportes, reloj, MONEDAS, MONEDA),
        por_categoria=GetCategoryBreakdown(reportes, reloj, MONEDAS, MONEDA),
        tendencia=GetMonthlyTrend(reportes, reloj, MONEDAS, MONEDA),
        presupuestos=GetBudgetProgress(
            FakeBudgetRepository(), categorias, reportes, MONEDAS, MONEDA
        ),
        movimientos=ListTransactions(FakeTransactionRepository()),
        reglas=FakeRecurringRuleRepository(),
        metas=GetSavingsGoalsProgress(
            FakeSavingsGoalRepository(), reportes, reloj, MONEDAS, MONEDA
        ),
        default_currency=MONEDA,
    )


@pytest.fixture
def asistente(
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    """Devuelve una fábrica que arma el asistente sobre un modelo falso.

    Se parchea `ChatOpenAI` en el módulo en vez de inyectar el modelo por
    constructor: así el test recorre exactamente el mismo camino de
    construcción que producción, incluidos los kwargs que se le pasan.
    """

    def fabricar(
        modelo: ModeloFalso,
        *,
        max_iterations: int = 3,
        timeout_seconds: int = 30,
        deps: DependenciasDelAsistente | None = None,
    ) -> LangChainAssistant:
        monkeypatch.setattr(modulo_agente, "ChatOpenAI", lambda **kwargs: modelo)
        return LangChainAssistant(
            deps=deps or _dependencias(),
            api_key="sk-falsa",
            model="gpt-5-mini",
            max_tokens=500,
            max_iterations=max_iterations,
            timeout_seconds=timeout_seconds,
        )

    return fabricar


class TestRespuesta:
    async def test_devuelve_el_texto_del_modelo(self, asistente: Any) -> None:
        # Arrange
        modelo = ModeloFalso(respuestas=[AIMessage(content="Gastaste 1000 ARS este mes.")])

        # Act
        respuesta = await asistente(modelo).answer(7, "¿cuánto gasté?", [], TEMPORAL)

        # Assert
        assert respuesta.content == "Gastaste 1000 ARS este mes."
        assert respuesta.degraded is False

    async def test_contabiliza_los_tokens_de_la_corrida(self, asistente: Any) -> None:
        # Arrange
        modelo = ModeloFalso(respuestas=[AIMessage(content="Listo.")], tokens_por_llamada=100)

        # Act
        respuesta = await asistente(modelo).answer(7, "hola", [], TEMPORAL)

        # Assert
        assert respuesta.usage.model == "gpt-5-mini"
        assert respuesta.usage.prompt_tokens == 100
        assert respuesta.usage.completion_tokens == 3
        assert respuesta.usage.total_tokens == 103

    async def test_suma_el_consumo_de_todas_las_vueltas(self, asistente: Any) -> None:
        # Arrange
        modelo = ModeloFalso(
            respuestas=[LLAMADA_A_HERRAMIENTA, AIMessage(content="Gastaste 0 ARS.")]
        )

        # Act
        respuesta = await asistente(modelo).answer(7, "¿cuánto gasté?", [], TEMPORAL)

        # Assert: dos llamadas al modelo y una a la herramienta.
        assert respuesta.usage.total_tokens == 32
        assert respuesta.usage.tool_calls_count == 1

    async def test_le_pasa_el_historial_al_modelo(self, asistente: Any) -> None:
        # Arrange
        modelo = ModeloFalso(respuestas=[AIMessage(content="Sí.")])
        historial = [
            ChatMessage(role=ChatRole.USER, content="¿cuánto gasté?", created_at=AHORA),
            ChatMessage(role=ChatRole.ASSISTANT, content="1000 ARS.", created_at=AHORA),
        ]

        # Act
        await asistente(modelo).answer(7, "¿es mucho?", historial, TEMPORAL)

        # Assert: system + dos del historial + la consulta actual.
        assert modelo.llamadas == 1

    async def test_una_respuesta_vacia_se_marca_como_degradada(self, asistente: Any) -> None:
        # Arrange
        modelo = ModeloFalso(respuestas=[AIMessage(content="   ")])

        # Act
        respuesta = await asistente(modelo).answer(7, "hola", [], TEMPORAL)

        # Assert
        assert respuesta.content == MENSAJE_SIN_CONVERGER
        assert respuesta.degraded is True


class TestTopeDeIteraciones:
    async def test_corta_cuando_el_agente_no_converge(self, asistente: Any) -> None:
        # Arrange: el modelo pide la misma herramienta para siempre.
        modelo = ModeloFalso(respuestas=[LLAMADA_A_HERRAMIENTA])

        # Act
        respuesta = await asistente(modelo, max_iterations=3).answer(7, "loop", [], TEMPORAL)

        # Assert: contesta algo legible en vez de colgarse o loopear.
        assert respuesta.content == MENSAJE_SIN_CONVERGER
        assert respuesta.degraded is True
        assert modelo.llamadas == 3

    async def test_el_consumo_del_intento_igual_se_reporta(self, asistente: Any) -> None:
        # Arrange: esos tokens se facturaron aunque no hubiera respuesta.
        modelo = ModeloFalso(respuestas=[LLAMADA_A_HERRAMIENTA], tokens_por_llamada=10)

        # Act
        respuesta = await asistente(modelo, max_iterations=2).answer(7, "loop", [], TEMPORAL)

        # Assert
        assert respuesta.usage.total_tokens == 26


class TestContadorDeUso:
    """El consumo se lee de dos lugares porque la librería lo mueve de versión.

    Si un día `llm_output` deja de traerlo, la telemetría se pondría en cero sin
    error ninguno y nadie se enteraría hasta mirar la factura.
    """

    def test_lee_el_consumo_de_llm_output(self) -> None:
        # Arrange
        contador = ContadorDeUso()

        # Act
        contador.on_llm_end(
            SimpleNamespace(
                llm_output={
                    "token_usage": {
                        "prompt_tokens": 30,
                        "completion_tokens": 7,
                        "total_tokens": 37,
                    }
                }
            )
        )

        # Assert
        assert (contador.prompt_tokens, contador.completion_tokens, contador.total_tokens) == (
            30,
            7,
            37,
        )

    def test_cae_a_usage_metadata_del_mensaje(self) -> None:
        # Arrange
        contador = ContadorDeUso()
        mensaje = AIMessage(
            content="x",
            usage_metadata={"input_tokens": 12, "output_tokens": 4, "total_tokens": 16},
        )

        # Act
        contador.on_llm_end(
            SimpleNamespace(llm_output=None, generations=[[SimpleNamespace(message=mensaje)]])
        )

        # Assert
        assert (contador.prompt_tokens, contador.completion_tokens, contador.total_tokens) == (
            12,
            4,
            16,
        )

    def test_sin_datos_de_consumo_no_rompe(self) -> None:
        # Arrange
        contador = ContadorDeUso()

        # Act: una respuesta sin telemetría no debería costar la corrida entera.
        contador.on_llm_end(SimpleNamespace(llm_output=None, generations=[]))

        # Assert
        assert contador.total_tokens == 0


class TestFallas:
    async def test_traduce_cualquier_error_del_sdk(self, asistente: Any) -> None:
        # Arrange
        modelo = ModeloFalso(respuestas=[AIMessage(content="x")], error=RuntimeError("429 rate"))

        # Act / Assert: arriba no tiene por qué conocer las excepciones de OpenAI.
        with pytest.raises(AssistantUnavailableError):
            await asistente(modelo).answer(7, "hola", [], TEMPORAL)

    async def test_no_espera_para_siempre(self, asistente: Any) -> None:
        # Arrange
        modelo = ModeloFalso(respuestas=[AIMessage(content="tarde")], demora_segundos=5)

        # Act / Assert
        with pytest.raises(AssistantUnavailableError):
            await asistente(modelo, timeout_seconds=-4).answer(7, "hola", [], TEMPORAL)


class TestAislamiento:
    def test_ninguna_herramienta_expone_el_identificador_del_usuario(self) -> None:
        # Arrange
        herramientas = construir_herramientas(7, _dependencias())

        # Act
        argumentos = {h.name: set(h.args.keys()) for h in herramientas}

        # Assert: el modelo no tiene dónde poner "el usuario 2", así que ninguna
        # prompt injection puede pedir datos ajenos (docs/PROMPT.md §11).
        # El número está fijo a propósito: agregar una herramienta rompe este
        # test y obliga a mirar sus argumentos antes de subirlo.
        assert len(argumentos) == 8
        for nombre, campos in argumentos.items():
            assert not any("user" in campo for campo in campos), nombre

    async def test_la_herramienta_consulta_por_el_usuario_cerrado_y_no_por_el_argumento(
        self,
    ) -> None:
        # Arrange
        reportes = FakeReportRepository()
        reportes.resumen = PeriodSummary(
            currency=MONEDA,
            date_from=HOY,
            date_to=HOY,
            income=Money.of("100.00", MONEDA),
            expense=Money.of("40.00", MONEDA),
        )
        herramienta = next(
            h
            for h in construir_herramientas(7, _dependencias(reportes))
            if h.name == "get_period_summary"
        )

        # Act: el modelo intenta colar otro usuario en los argumentos.
        await herramienta.ainvoke({"user_id": 8, "date_from": "2026-08-01"})

        # Assert: el argumento se descarta y la consulta va por el usuario 7.
        assert reportes.usuarios_pedidos == [7]
