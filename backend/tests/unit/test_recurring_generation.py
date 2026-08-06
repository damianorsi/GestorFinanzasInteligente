"""Tests del job de generación de movimientos recurrentes.

Se testea el caso de uso, no APScheduler: el scheduler solo lo llama
(docs/PROMPT.md §9).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.application.use_cases.recurring import GenerateRecurringTransactions
from app.domain.entities import Category, RecurringRule
from app.domain.enums import OccurrenceStatus, RecurrenceFrequency, TransactionType
from app.domain.value_objects import Money
from tests.fakes import (
    FakeCategoryRepository,
    FakeRecurringOccurrenceRepository,
    FakeRecurringRuleRepository,
)

MONEDA = "ARS"
HOY = date(2026, 8, 5)
CATCHUP = 90

LOGGER_DEL_JOB = "app.application.use_cases.recurring.generate"


class _Coleccionista(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.registros: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.registros.append(record)

    @property
    def mensajes(self) -> str:
        return "\n".join(registro.getMessage() for registro in self.registros)


@contextmanager
def _capturando(nombre: str) -> Iterator[_Coleccionista]:
    """Captura los warnings de un logger concreto.

    Se usa un handler propio en vez de `caplog` porque `configure_logging`
    reemplaza los handlers del root al importar la aplicación, y eso deja
    afuera al de caplog para el resto de la sesión: el test pasa con el archivo
    aislado y falla en la suite completa. Un handler propio no depende del
    estado global del logging.
    """
    logger = logging.getLogger(nombre)
    nivel_previo = logger.level
    handler = _Coleccionista()
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(nivel_previo)


class _RepositorioQueExplota(FakeRecurringOccurrenceRepository):
    """Falla al registrar las ocurrencias de una regla puntual."""

    def __init__(self, rule_id_que_falla: int) -> None:
        super().__init__()
        self._rule_id_que_falla = rule_id_que_falla

    async def register_generated(self, transaction, occurred_on):  # type: ignore[no-untyped-def]
        if transaction.recurring_rule_id == self._rule_id_que_falla:
            raise RuntimeError("la base dijo que no")
        return await super().register_generated(transaction, occurred_on)


class _Escenario:
    """Arma el job con fakes y expone lo necesario para las aserciones."""

    def __init__(
        self,
        *,
        catchup: int = CATCHUP,
        occurrences: FakeRecurringOccurrenceRepository | None = None,
    ) -> None:
        self.rules = FakeRecurringRuleRepository()
        self.occurrences = occurrences or FakeRecurringOccurrenceRepository()
        self.categories = FakeCategoryRepository()
        self.caso = GenerateRecurringTransactions(
            rules=self.rules,
            occurrences=self.occurrences,
            categories=self.categories,
            catchup_max_days=catchup,
        )

    def con_categoria(self, category_id: int = 1, user_id: int = 1) -> None:
        self.categories.categorias.append(
            Category(
                id=category_id,
                user_id=user_id,
                name="Alquiler",
                type=TransactionType.EXPENSE,
            )
        )

    def con_regla(
        self,
        *,
        user_id: int = 1,
        category_id: int = 1,
        frecuencia: RecurrenceFrequency = RecurrenceFrequency.MONTHLY,
        starts_on: date = date(2026, 6, 10),
        day_of_month: int | None = 10,
        day_of_week: int | None = None,
        ends_on: date | None = None,
        is_active: bool = True,
        monto: str = "45000.00",
    ) -> RecurringRule:
        return self.rules.agregar(
            RecurringRule(
                user_id=user_id,
                category_id=category_id,
                type=TransactionType.EXPENSE,
                money=Money(Decimal(monto), MONEDA),
                frequency=frecuencia,
                starts_on=starts_on,
                description="Alquiler",
                day_of_month=day_of_month,
                day_of_week=day_of_week,
                ends_on=ends_on,
                is_active=is_active,
            )
        )


@pytest.fixture
def escenario() -> _Escenario:
    entorno = _Escenario()
    entorno.con_categoria()
    return entorno


class TestGeneracion:
    async def test_materializa_las_fechas_pendientes(self, escenario: _Escenario) -> None:
        # Arrange: regla del día 10, y hoy es 5 de agosto.
        escenario.con_regla(starts_on=date(2026, 6, 10))

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert: junio y julio. El 10 de agosto todavía no llegó.
        assert resultado.generated == 2
        assert [m.occurred_on for m in escenario.occurrences.movimientos] == [
            date(2026, 6, 10),
            date(2026, 7, 10),
        ]

    async def test_el_movimiento_generado_lleva_los_datos_de_la_regla(
        self, escenario: _Escenario
    ) -> None:
        # Arrange
        regla = escenario.con_regla(starts_on=date(2026, 8, 1), day_of_month=1, monto="45000.00")

        # Act
        await escenario.caso.execute(HOY)

        # Assert
        movimiento = escenario.occurrences.movimientos[0]
        assert movimiento.recurring_rule_id == regla.id
        assert movimiento.money == Money(Decimal("45000.00"), MONEDA)
        assert movimiento.category_id == regla.category_id
        assert movimiento.description == "Alquiler"

    async def test_nunca_materializa_el_futuro(self, escenario: _Escenario) -> None:
        # Arrange: una regla diaria arrancada hace tiempo.
        escenario.con_regla(
            frecuencia=RecurrenceFrequency.DAILY,
            starts_on=date(2026, 8, 1),
            day_of_month=None,
        )

        # Act
        await escenario.caso.execute(HOY)

        # Assert: materializar el sueldo del día 1 por adelantado haría que el
        # balance de hoy muestre plata que todavía no se cobró.
        assert all(m.occurred_on <= HOY for m in escenario.occurrences.movimientos)
        assert max(m.occurred_on for m in escenario.occurrences.movimientos) == HOY

    async def test_una_regla_que_termino_no_genera_mas(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_regla(starts_on=date(2026, 6, 10), ends_on=date(2026, 7, 10))

        # Act
        await escenario.caso.execute(HOY)

        # Assert
        assert [m.occurred_on for m in escenario.occurrences.movimientos] == [
            date(2026, 6, 10),
            date(2026, 7, 10),
        ]

    async def test_una_regla_pausada_no_genera(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_regla(is_active=False)

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert
        assert resultado.generated == 0
        assert resultado.rules_processed == 0


class TestIdempotencia:
    async def test_correrlo_tres_veces_genera_lo_mismo_que_una(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_regla(starts_on=date(2026, 6, 10))

        # Act
        primera = await escenario.caso.execute(HOY)
        await escenario.caso.execute(HOY)
        tercera = await escenario.caso.execute(HOY)

        # Assert: el job tiene que poder correr cincuenta veces sin duplicar
        # un solo movimiento.
        assert primera.generated == 2
        assert tercera.generated == 0
        assert tercera.already_resolved == 2
        assert len(escenario.occurrences.movimientos) == 2

    async def test_una_ocurrencia_salteada_no_revive(self, escenario: _Escenario) -> None:
        # Arrange: se genera y después se borra el movimiento, como cuando
        # alguien borra el alquiler de un mes a mano.
        escenario.con_regla(starts_on=date(2026, 6, 10))
        await escenario.caso.execute(HOY)
        borrado = escenario.occurrences.movimientos[1]
        await escenario.occurrences.mark_skipped_by_transaction(borrado.id or 0)

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert: si el alquiler borrado reapareciera al otro día, el libro
        # mayor estaría mal implementado. Es el bug más probable de la feature.
        assert resultado.generated == 0
        ocurrencia = escenario.occurrences.ocurrencias[
            (borrado.recurring_rule_id or 0, borrado.occurred_on)
        ]
        assert ocurrencia.status is OccurrenceStatus.SKIPPED

    async def test_si_otra_corrida_gana_la_carrera_no_se_duplica(
        self, escenario: _Escenario
    ) -> None:
        # Arrange: se simula que la ocurrencia ya está registrada por otra
        # corrida, que es lo que devuelve la UNIQUE de la base.
        regla = escenario.con_regla(starts_on=date(2026, 8, 1), day_of_month=1)
        await escenario.occurrences.mark_skipped(regla.id or 0, [date(2026, 8, 1)])

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert
        assert resultado.generated == 0
        assert resultado.already_resolved == 1


class TestCatchUp:
    async def test_recorta_la_ventana_al_tope_de_dias(self) -> None:
        # Arrange: una regla diaria arrancada 200 días atrás.
        entorno = _Escenario(catchup=CATCHUP)
        entorno.con_categoria()
        entorno.con_regla(
            frecuencia=RecurrenceFrequency.DAILY,
            starts_on=HOY - timedelta(days=200),
            day_of_month=None,
        )

        # Act
        resultado = await entorno.caso.execute(HOY)

        # Assert: un contenedor apagado ocho meses no puede inyectar cientos de
        # movimientos de golpe. La ventana es [hoy-90, hoy], o sea 91 días.
        assert resultado.generated == CATCHUP + 1
        assert min(m.occurred_on for m in entorno.occurrences.movimientos) == HOY - timedelta(
            days=CATCHUP
        )

    async def test_avisa_cuando_recorta(self) -> None:
        # Arrange
        entorno = _Escenario()
        entorno.con_categoria()
        regla = entorno.con_regla(
            frecuencia=RecurrenceFrequency.DAILY,
            starts_on=HOY - timedelta(days=200),
            day_of_month=None,
        )

        # Act
        with _capturando(LOGGER_DEL_JOB) as registros:
            resultado = await entorno.caso.execute(HOY)

        # Assert: un recorte silencioso dejaría un hueco de movimientos sin que
        # nadie se entere de que la aplicación estuvo caída.
        assert resultado.rules_truncated == [regla.id]
        assert "Catch-up recortado" in registros.mensajes

    async def test_no_recorta_si_la_regla_es_reciente(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_regla(starts_on=HOY - timedelta(days=10), day_of_month=1)

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert
        assert resultado.rules_truncated == []


class TestAislamientoDeFallos:
    async def test_una_regla_sin_categoria_se_desactiva_y_las_otras_siguen(self) -> None:
        # Arrange: la segunda regla apunta a una categoría que no existe.
        entorno = _Escenario()
        entorno.con_categoria(category_id=1)
        buena = entorno.con_regla(category_id=1, starts_on=date(2026, 8, 1), day_of_month=1)
        huerfana = entorno.con_regla(category_id=999, starts_on=date(2026, 8, 1), day_of_month=1)

        # Act
        resultado = await entorno.caso.execute(HOY)

        # Assert
        assert resultado.generated == 1
        assert resultado.rules_deactivated == 1
        assert escenario_regla(entorno, buena.id or 0).is_active is True
        assert escenario_regla(entorno, huerfana.id or 0).is_active is False

    async def test_una_regla_que_explota_no_voltea_a_las_demas(self) -> None:
        # Arrange
        entorno = _Escenario()
        entorno.con_categoria()
        rota = entorno.con_regla(starts_on=date(2026, 8, 1), day_of_month=1)
        entorno.occurrences = _RepositorioQueExplota(rota.id or 0)
        entorno.caso = GenerateRecurringTransactions(
            rules=entorno.rules,
            occurrences=entorno.occurrences,
            categories=entorno.categories,
            catchup_max_days=CATCHUP,
        )
        entorno.con_regla(starts_on=date(2026, 8, 2), day_of_month=2)

        # Act
        resultado = await entorno.caso.execute(HOY)

        # Assert: procesar regla por regla con manejo de error individual es el
        # requisito; una regla rota no puede dejar sin generar a las demás.
        assert resultado.rules_failed == 1
        assert resultado.generated == 1

    async def test_el_resultado_reporta_lo_que_paso(self, escenario: _Escenario) -> None:
        # Arrange
        escenario.con_regla(starts_on=date(2026, 8, 1), day_of_month=1)

        # Act
        resultado = await escenario.caso.execute(HOY)

        # Assert
        assert resultado.as_of == HOY
        assert resultado.rules_processed == 1
        assert resultado.rules_failed == 0
        assert resultado.rules_deactivated == 0


class TestMultiusuario:
    async def test_cada_movimiento_queda_a_nombre_del_dueno_de_la_regla(self) -> None:
        # Arrange
        entorno = _Escenario()
        entorno.con_categoria(category_id=1, user_id=1)
        entorno.con_categoria(category_id=2, user_id=2)
        entorno.con_regla(user_id=1, category_id=1, starts_on=date(2026, 8, 1), day_of_month=1)
        entorno.con_regla(user_id=2, category_id=2, starts_on=date(2026, 8, 1), day_of_month=1)

        # Act
        await entorno.caso.execute(HOY)

        # Assert
        assert {m.user_id for m in entorno.occurrences.movimientos} == {1, 2}
        for movimiento in entorno.occurrences.movimientos:
            regla = next(r for r in entorno.rules.reglas if r.id == movimiento.recurring_rule_id)
            assert movimiento.user_id == regla.user_id


def escenario_regla(entorno: _Escenario, rule_id: int) -> RecurringRule:
    return next(regla for regla in entorno.rules.reglas if regla.id == rule_id)
