"""Tests del job de alertas proactivas (docs/PROMPT.md §14 y §21.2)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

import pytest

from app.application.dtos import (
    AssistantAnswer,
    ChatMessage,
    TemporalContext,
    TokenUsage,
)
from app.application.exceptions import AssistantUnavailableError
from app.application.use_cases.alerts import GenerateBudgetAlerts
from app.application.use_cases.budgets import GetBudgetProgress
from app.domain.entities import Category
from app.domain.enums import AlertStatus, AlertType, TransactionType
from app.domain.value_objects import Money
from tests.fakes import (
    FakeBudgetAlertRepository,
    FakeBudgetRepository,
    FakeCategoryRepository,
    FakeReportRepository,
)

MONEDAS = frozenset({"ARS"})
MONEDA = "ARS"
USUARIO = 1
PERIODO = date(2026, 8, 1)
# Día 10: ya se puede proyectar y todavía queda mes por delante.
HOY = date(2026, 8, 10)
MINIMO_SIN_TOPE = Decimal("10000")


class AgenteFalso:
    def __init__(self, texto: str = "Recortá salidas por dos semanas.") -> None:
        self.texto = texto
        self.error: Exception | None = None
        self.degradado = False
        self.consultas: list[str] = []

    async def answer(
        self,
        user_id: int,
        message: str,
        history: Sequence[ChatMessage],
        temporal: TemporalContext,
    ) -> AssistantAnswer:
        self.consultas.append(message)
        if self.error is not None:
            raise self.error
        return AssistantAnswer(
            content=self.texto, usage=TokenUsage(model="gpt-5-mini"), degraded=self.degradado
        )


class _Escenario:
    """Arma el job con fakes, con un presupuesto de Alimentación cargado."""

    def __init__(self, *, agente: AgenteFalso | None = None, max_recomendaciones: int = 10) -> None:
        self.reportes = FakeReportRepository()
        self.presupuestos = FakeBudgetRepository()
        self.alertas = FakeBudgetAlertRepository()
        self.categorias = FakeCategoryRepository()
        self.categorias.categorias.append(
            Category(id=1, user_id=USUARIO, name="Alimentación", type=TransactionType.EXPENSE)
        )
        self.agente = agente
        self.caso = GenerateBudgetAlerts(
            budgets=self.presupuestos,
            alerts=self.alertas,
            progress=GetBudgetProgress(
                self.presupuestos, self.categorias, self.reportes, MONEDAS, MONEDA
            ),
            currency=MONEDA,
            minimo_sin_presupuesto=MINIMO_SIN_TOPE,
            agent=agente,
            max_recomendaciones=max_recomendaciones,
        )

    def con_presupuesto(self, tope: str, gastado: str, category_id: int = 1) -> None:
        from app.application.dtos import CategoryTotal
        from app.domain.entities import Budget

        self.presupuestos.agregar(
            Budget(
                user_id=USUARIO,
                category_id=category_id,
                period_month=PERIODO,
                limit=Money(Decimal(tope), MONEDA),
            )
        )
        self.reportes.por_categoria.append(
            CategoryTotal(
                category_id=category_id,
                category_name="Alimentación",
                type=TransactionType.EXPENSE,
                total=Money(Decimal(gastado), MONEDA),
                transaction_count=3,
            )
        )

    def con_gasto_sin_presupuesto(self, gastado: str, category_id: int = 9) -> None:
        from app.application.dtos import CategoryTotal

        self.categorias.categorias.append(
            Category(id=category_id, user_id=USUARIO, name="Ocio", type=TransactionType.EXPENSE)
        )
        self.reportes.por_categoria.append(
            CategoryTotal(
                category_id=category_id,
                category_name="Ocio",
                type=TransactionType.EXPENSE,
                total=Money(Decimal(gastado), MONEDA),
                transaction_count=2,
            )
        )


@pytest.fixture
def escenario() -> _Escenario:
    return _Escenario()


class TestDeteccion:
    async def test_emite_una_alerta_cuando_se_paso(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_presupuesto(tope="100000.00", gastado="130000.00")

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert
        assert resultado.created == 1
        alerta = escenario.alertas.alertas[0]
        assert alerta.type is AlertType.BUDGET_EXCEEDED
        assert "Te pasaste" in alerta.message

    async def test_emite_una_alerta_de_riesgo_antes_de_pasarse(self, escenario: _Escenario) -> None:
        # Arrange: 60.000 de 100.000 al día 10 proyecta 186%.
        escenario.con_presupuesto(tope="100000.00", gastado="60000.00")

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert: es la que hace proactiva la feature.
        assert resultado.created == 1
        alerta = escenario.alertas.alertas[0]
        assert alerta.type is AlertType.BUDGET_AT_RISK
        assert alerta.projected_percentage == Decimal("186.00")
        assert "186.00%" in alerta.message

    async def test_un_presupuesto_sano_no_genera_nada(self, escenario: _Escenario) -> None:
        # Arrange: 20.000 de 100.000 al día 10 proyecta 62%.
        escenario.con_presupuesto(tope="100000.00", gastado="20000.00")

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert
        assert resultado.created == 0

    async def test_avisa_de_una_categoria_sin_presupuesto(self, escenario: _Escenario) -> None:
        # Arrange: tiene un presupuesto sano y además gasta en una categoría
        # sin tope.
        escenario.con_presupuesto(tope="100000.00", gastado="20000.00")
        escenario.con_gasto_sin_presupuesto(gastado="40000.00")

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert
        assert resultado.created == 1
        assert escenario.alertas.alertas[0].type is AlertType.UNBUDGETED_SPENDING

    async def test_ignora_un_gasto_sin_presupuesto_que_es_menor(
        self, escenario: _Escenario
    ) -> None:
        # Arrange: por debajo del mínimo configurado.
        escenario.con_presupuesto(tope="100000.00", gastado="20000.00")
        escenario.con_gasto_sin_presupuesto(gastado="500.00")

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert: avisar por cualquier gasto llenaría la bandeja de ruido.
        assert resultado.created == 0

    async def test_quien_no_tiene_ningun_presupuesto_no_recibe_alertas(
        self, escenario: _Escenario
    ) -> None:
        # Arrange: solo gasto, sin ningún tope definido.
        escenario.con_gasto_sin_presupuesto(gastado="40000.00")

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert: alcance deliberado. Avisarle a alguien que no usa la función
        # es consejo no pedido, y recorrer a todos los usuarios activos sería
        # calcular el avance completo de cada uno todos los días.
        assert resultado.users_processed == 0
        assert resultado.created == 0


class TestIdempotencia:
    async def test_correrlo_tres_veces_deja_las_mismas_alertas(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_presupuesto(tope="100000.00", gastado="130000.00")

        # Act
        primera = await escenario.caso.execute(HOY)
        await escenario.caso.execute(HOY)
        tercera = await escenario.caso.execute(HOY)

        # Assert: si no, la persona vería la misma alerta todos los días.
        assert primera.created == 1
        assert tercera.created == 0
        assert tercera.already_open == 1
        assert len(escenario.alertas.alertas) == 1

    async def test_no_regenera_la_recomendacion_de_una_alerta_que_ya_existia(self) -> None:
        # Arrange
        agente = AgenteFalso()
        entorno = _Escenario(agente=agente)
        entorno.con_presupuesto(tope="100000.00", gastado="130000.00")
        await entorno.caso.execute(HOY)

        # Act
        await entorno.caso.execute(HOY)

        # Assert: cada recomendación es una corrida completa del agente;
        # rehacerla todos los días sería pagar por lo mismo.
        assert len(agente.consultas) == 1

    async def test_una_alerta_leida_tampoco_se_vuelve_a_emitir(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_presupuesto(tope="100000.00", gastado="130000.00")
        await escenario.caso.execute(HOY)
        escenario.alertas.alertas[0].marcar_leida()

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert
        assert resultado.created == 0
        assert escenario.alertas.alertas[0].status is AlertStatus.READ


class TestResolucion:
    async def test_una_alerta_que_dejo_de_aplicar_se_resuelve(self) -> None:
        # Arrange: primero se pasa del tope.
        entorno = _Escenario()
        entorno.con_presupuesto(tope="100000.00", gastado="130000.00")
        await entorno.caso.execute(HOY)

        # Act: sube el tope y el desvío deja de ser cierto.
        presupuesto = next(iter(entorno.presupuestos.presupuestos.values()))
        presupuesto.limit = Money(Decimal("500000.00"), MONEDA)
        resultado = await entorno.caso.execute(HOY)

        # Assert: se marca resuelta, no se borra. Borrarla haría que el job la
        # volviera a emitir mañana.
        assert resultado.resolved == 1
        assert entorno.alertas.alertas[0].status is AlertStatus.RESOLVED


class TestRecomendacion:
    async def test_el_agente_redacta_que_hacer(self) -> None:
        # Arrange
        agente = AgenteFalso("Bajá las salidas dos semanas y cocina en casa.")
        entorno = _Escenario(agente=agente)
        entorno.con_presupuesto(tope="100000.00", gastado="130000.00")

        # Act
        resultado = await entorno.caso.execute(HOY)

        # Assert: la detección es una regla; qué hacer al respecto es lo que
        # vuelve IA a la feature.
        assert resultado.recommendations == 1
        assert (
            entorno.alertas.alertas[0].recommendation
            == "Bajá las salidas dos semanas y cocina en casa."
        )

    async def test_con_el_agente_caido_la_alerta_se_emite_igual(self) -> None:
        # Arrange
        agente = AgenteFalso()
        agente.error = AssistantUnavailableError("OpenAI caído.")
        entorno = _Escenario(agente=agente)
        entorno.con_presupuesto(tope="100000.00", gastado="130000.00")

        # Act
        resultado = await entorno.caso.execute(HOY)

        # Assert: saber que te estás pasando no depende de que el modelo esté
        # disponible.
        assert resultado.created == 1
        assert resultado.recommendations == 0
        assert entorno.alertas.alertas[0].recommendation is None

    async def test_una_respuesta_degradada_no_se_guarda_como_recomendacion(self) -> None:
        # Arrange
        agente = AgenteFalso()
        agente.degradado = True
        entorno = _Escenario(agente=agente)
        entorno.con_presupuesto(tope="100000.00", gastado="130000.00")

        # Act
        await entorno.caso.execute(HOY)

        # Assert: el texto de fallback no es una recomendación.
        assert entorno.alertas.alertas[0].recommendation is None

    async def test_sin_agente_las_alertas_salen_igual(self) -> None:
        # Arrange: es el caso de no tener API key configurada.
        entorno = _Escenario(agente=None)
        entorno.con_presupuesto(tope="100000.00", gastado="130000.00")

        # Act
        resultado = await entorno.caso.execute(HOY)

        # Assert
        assert resultado.created == 1
        assert entorno.alertas.alertas[0].recommendation is None

    async def test_respeta_el_tope_de_recomendaciones_por_corrida(self) -> None:
        # Arrange: dos desvíos y presupuesto para una sola recomendación.
        agente = AgenteFalso()
        entorno = _Escenario(agente=agente, max_recomendaciones=1)
        entorno.con_presupuesto(tope="100000.00", gastado="130000.00", category_id=1)
        entorno.con_presupuesto(tope="50000.00", gastado="90000.00", category_id=2)
        entorno.categorias.categorias.append(
            Category(id=2, user_id=USUARIO, name="Transporte", type=TransactionType.EXPENSE)
        )

        # Act
        resultado = await entorno.caso.execute(HOY)

        # Assert: las dos alertas salen; solo una lleva recomendación.
        assert resultado.created == 2
        assert resultado.recommendations == 1
        assert len(agente.consultas) == 1

    async def test_las_categorias_sin_presupuesto_no_consultan_al_agente(self) -> None:
        # Arrange
        agente = AgenteFalso()
        entorno = _Escenario(agente=agente)
        entorno.con_gasto_sin_presupuesto(gastado="40000.00")

        # Act
        await entorno.caso.execute(HOY)

        # Assert: qué hacer ya lo dice el mensaje —definir un tope—, y gastar
        # una corrida del agente para repetirlo no aporta.
        assert agente.consultas == []


class TestAislamientoDeFallos:
    async def test_un_usuario_que_falla_no_deja_sin_alertas_a_los_demas(self) -> None:
        # Arrange
        entorno = _Escenario()
        entorno.con_presupuesto(tope="100000.00", gastado="130000.00")
        entorno.presupuestos.usuarios_con_presupuesto = [99, USUARIO]
        entorno.alertas.fallar_para_usuario = 99

        # Act
        resultado = await entorno.caso.execute(HOY)

        # Assert
        assert resultado.users_failed == 1
        assert resultado.created == 1
