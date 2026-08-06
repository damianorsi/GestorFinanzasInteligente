"""Tests de los casos de uso del ABM de reglas recurrentes y la proyección."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.application.exceptions import (
    InvalidReferenceError,
    ResourceNotFoundError,
    UnsupportedCurrencyError,
)
from app.application.use_cases.recurring import (
    CreateRecurringRule,
    DeleteRecurringRule,
    GetRuleOccurrences,
    GetUpcomingOccurrences,
    ListRecurringRules,
    UpdateRecurringRule,
)
from app.domain.entities import Category, RecurringRule
from app.domain.enums import OccurrenceStatus, RecurrenceFrequency, TransactionType
from app.domain.value_objects import Money
from tests.fakes import (
    FakeCategoryRepository,
    FakeRecurringOccurrenceRepository,
    FakeRecurringRuleRepository,
    FixedClock,
)

MONEDAS = frozenset({"ARS"})
MONEDA = "ARS"
HOY = date(2026, 8, 5)
AHORA = datetime(2026, 8, 5, 12, 0, 0)
CATCHUP = 90

USUARIO = 1
AJENO = 2


@pytest.fixture
def categorias() -> FakeCategoryRepository:
    repo = FakeCategoryRepository()
    repo.categorias.extend(
        [
            Category(id=1, user_id=USUARIO, name="Servicios", type=TransactionType.EXPENSE),
            Category(id=2, user_id=USUARIO, name="Sueldo", type=TransactionType.INCOME),
            Category(id=3, user_id=AJENO, name="Ajena", type=TransactionType.EXPENSE),
        ]
    )
    return repo


@pytest.fixture
def reglas() -> FakeRecurringRuleRepository:
    return FakeRecurringRuleRepository()


@pytest.fixture
def ocurrencias() -> FakeRecurringOccurrenceRepository:
    return FakeRecurringOccurrenceRepository()


def _crear(
    reglas: FakeRecurringRuleRepository, categorias: FakeCategoryRepository
) -> CreateRecurringRule:
    return CreateRecurringRule(reglas, categorias, MONEDAS, MONEDA)


def _editar(
    reglas: FakeRecurringRuleRepository,
    categorias: FakeCategoryRepository,
    ocurrencias: FakeRecurringOccurrenceRepository,
) -> UpdateRecurringRule:
    return UpdateRecurringRule(
        reglas, categorias, ocurrencias, FixedClock(AHORA), MONEDAS, MONEDA, CATCHUP
    )


def _regla_de(
    reglas: FakeRecurringRuleRepository,
    *,
    user_id: int = USUARIO,
    category_id: int = 1,
    frecuencia: RecurrenceFrequency = RecurrenceFrequency.MONTHLY,
    starts_on: date = date(2026, 1, 10),
    day_of_month: int | None = 10,
    day_of_week: int | None = None,
    is_active: bool = True,
    tipo: TransactionType = TransactionType.EXPENSE,
    monto: str = "45000.00",
) -> RecurringRule:
    return reglas.agregar(
        RecurringRule(
            user_id=user_id,
            category_id=category_id,
            type=tipo,
            money=Money(Decimal(monto), MONEDA),
            frequency=frecuencia,
            starts_on=starts_on,
            description="Alquiler",
            day_of_month=day_of_month,
            day_of_week=day_of_week,
            is_active=is_active,
        )
    )


class TestAlta:
    async def test_crea_la_regla(
        self, reglas: FakeRecurringRuleRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Act
        regla = await _crear(reglas, categorias).execute(
            user_id=USUARIO,
            category_id=1,
            type=TransactionType.EXPENSE,
            amount=Decimal("45000.00"),
            frequency=RecurrenceFrequency.MONTHLY,
            starts_on=date(2026, 8, 1),
            day_of_month=10,
        )

        # Assert
        assert regla.id is not None
        assert regla.money == Money(Decimal("45000.00"), MONEDA)

    async def test_rechaza_una_categoria_del_otro_tipo(
        self, reglas: FakeRecurringRuleRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Act / Assert: una regla de gasto sobre la categoría del sueldo
        # generaría movimientos que contradicen su propia categoría.
        with pytest.raises(InvalidReferenceError, match="ingreso"):
            await _crear(reglas, categorias).execute(
                user_id=USUARIO,
                category_id=2,
                type=TransactionType.EXPENSE,
                amount=Decimal("1000.00"),
                frequency=RecurrenceFrequency.MONTHLY,
                starts_on=date(2026, 8, 1),
                day_of_month=10,
            )

    async def test_rechaza_una_categoria_ajena(
        self, reglas: FakeRecurringRuleRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Act / Assert
        with pytest.raises(InvalidReferenceError):
            await _crear(reglas, categorias).execute(
                user_id=USUARIO,
                category_id=3,
                type=TransactionType.EXPENSE,
                amount=Decimal("1000.00"),
                frequency=RecurrenceFrequency.MONTHLY,
                starts_on=date(2026, 8, 1),
                day_of_month=10,
            )

    async def test_rechaza_una_moneda_no_habilitada(
        self, reglas: FakeRecurringRuleRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Act / Assert
        with pytest.raises(UnsupportedCurrencyError):
            await _crear(reglas, categorias).execute(
                user_id=USUARIO,
                category_id=1,
                type=TransactionType.EXPENSE,
                amount=Decimal("1000.00"),
                frequency=RecurrenceFrequency.MONTHLY,
                starts_on=date(2026, 8, 1),
                day_of_month=10,
                currency="USD",
            )


class TestEdicion:
    async def test_cambiar_el_monto_no_toca_lo_ya_generado(
        self,
        reglas: FakeRecurringRuleRepository,
        categorias: FakeCategoryRepository,
        ocurrencias: FakeRecurringOccurrenceRepository,
    ) -> None:
        # Arrange
        regla = _regla_de(reglas)
        await ocurrencias.mark_skipped(regla.id or 0, [date(2026, 7, 10)])
        antes = dict(ocurrencias.ocurrencias)

        # Act
        actualizada = await _editar(reglas, categorias, ocurrencias).execute(
            USUARIO, regla.id or 0, amount=Decimal("50000.00")
        )

        # Assert: los movimientos de meses ya cerrados no se reescriben.
        assert actualizada.money == Money(Decimal("50000.00"), MONEDA)
        assert ocurrencias.ocurrencias == antes

    async def test_cambiar_de_frecuencia_limpia_el_dia_que_ya_no_aplica(
        self,
        reglas: FakeRecurringRuleRepository,
        categorias: FakeCategoryRepository,
        ocurrencias: FakeRecurringOccurrenceRepository,
    ) -> None:
        # Arrange
        regla = _regla_de(reglas, frecuencia=RecurrenceFrequency.MONTHLY, day_of_month=10)

        # Act
        actualizada = await _editar(reglas, categorias, ocurrencias).execute(
            USUARIO,
            regla.id or 0,
            frequency=RecurrenceFrequency.WEEKLY,
            day_of_week=2,
        )

        # Assert: arrastrar el `day_of_month` dejaría la regla inválida, porque
        # cada frecuencia rechaza los parámetros que no usa.
        assert actualizada.frequency is RecurrenceFrequency.WEEKLY
        assert actualizada.day_of_month is None
        assert actualizada.day_of_week == 2

    async def test_pausar_no_borra_las_ocurrencias(
        self,
        reglas: FakeRecurringRuleRepository,
        categorias: FakeCategoryRepository,
        ocurrencias: FakeRecurringOccurrenceRepository,
    ) -> None:
        # Arrange
        regla = _regla_de(reglas)
        await ocurrencias.mark_skipped(regla.id or 0, [date(2026, 7, 10)])

        # Act
        actualizada = await _editar(reglas, categorias, ocurrencias).execute(
            USUARIO, regla.id or 0, is_active=False
        )

        # Assert
        assert actualizada.is_active is False
        assert len(ocurrencias.ocurrencias) == 1

    async def test_reactivar_no_dispara_backfill_del_periodo_pausado(
        self,
        reglas: FakeRecurringRuleRepository,
        categorias: FakeCategoryRepository,
        ocurrencias: FakeRecurringOccurrenceRepository,
    ) -> None:
        # Arrange: una regla mensual pausada, arrancada en enero.
        regla = _regla_de(reglas, starts_on=date(2026, 1, 10), is_active=False)

        # Act
        await _editar(reglas, categorias, ocurrencias).execute(
            USUARIO, regla.id or 0, is_active=True
        )

        # Assert: las fechas del período de pausa quedan dadas por resueltas.
        # Sin esto, el job inyectaría de golpe los meses que nunca se pagaron.
        resueltas = await ocurrencias.resolved_dates(regla.id or 0)
        assert date(2026, 6, 10) in resueltas
        assert date(2026, 7, 10) in resueltas
        assert all(
            ocurrencia.status is OccurrenceStatus.SKIPPED
            for ocurrencia in ocurrencias.ocurrencias.values()
        )

    async def test_reactivar_no_marca_fechas_futuras(
        self,
        reglas: FakeRecurringRuleRepository,
        categorias: FakeCategoryRepository,
        ocurrencias: FakeRecurringOccurrenceRepository,
    ) -> None:
        # Arrange
        regla = _regla_de(reglas, starts_on=date(2026, 1, 10), is_active=False)

        # Act
        await _editar(reglas, categorias, ocurrencias).execute(
            USUARIO, regla.id or 0, is_active=True
        )

        # Assert: el 10 de agosto todavía no llegó, así que la regla lo tiene
        # que generar normalmente cuando llegue.
        resueltas = await ocurrencias.resolved_dates(regla.id or 0)
        assert date(2026, 8, 10) not in resueltas

    async def test_editar_sin_reactivar_no_toca_el_libro_mayor(
        self,
        reglas: FakeRecurringRuleRepository,
        categorias: FakeCategoryRepository,
        ocurrencias: FakeRecurringOccurrenceRepository,
    ) -> None:
        # Arrange
        regla = _regla_de(reglas, is_active=True)

        # Act
        await _editar(reglas, categorias, ocurrencias).execute(
            USUARIO, regla.id or 0, description="Alquiler nuevo"
        )

        # Assert
        assert ocurrencias.ocurrencias == {}

    async def test_no_deja_editar_una_regla_ajena(
        self,
        reglas: FakeRecurringRuleRepository,
        categorias: FakeCategoryRepository,
        ocurrencias: FakeRecurringOccurrenceRepository,
    ) -> None:
        # Arrange
        regla = _regla_de(reglas, user_id=AJENO, category_id=3)

        # Act / Assert: 404 y no 403, para no confirmar que el id existe.
        with pytest.raises(ResourceNotFoundError):
            await _editar(reglas, categorias, ocurrencias).execute(
                USUARIO, regla.id or 0, amount=Decimal("1.00")
            )


class TestBorrado:
    async def test_borra_la_regla(
        self, reglas: FakeRecurringRuleRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        regla = _regla_de(reglas)

        # Act
        await DeleteRecurringRule(reglas, categorias, MONEDAS, MONEDA).execute(
            USUARIO, regla.id or 0
        )

        # Assert
        assert reglas.reglas == []

    async def test_no_deja_borrar_una_regla_ajena(
        self, reglas: FakeRecurringRuleRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        regla = _regla_de(reglas, user_id=AJENO, category_id=3)

        # Act / Assert
        with pytest.raises(ResourceNotFoundError):
            await DeleteRecurringRule(reglas, categorias, MONEDAS, MONEDA).execute(
                USUARIO, regla.id or 0
            )


class TestListado:
    async def test_filtra_por_estado(
        self, reglas: FakeRecurringRuleRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        _regla_de(reglas, is_active=True)
        _regla_de(reglas, is_active=False)

        # Act
        activas = await ListRecurringRules(reglas, categorias, MONEDAS, MONEDA).execute(
            USUARIO, is_active=True
        )

        # Assert
        assert len(activas) == 1
        assert activas[0].is_active is True

    async def test_no_devuelve_reglas_ajenas(
        self, reglas: FakeRecurringRuleRepository, categorias: FakeCategoryRepository
    ) -> None:
        # Arrange
        _regla_de(reglas, user_id=AJENO, category_id=3)

        # Act
        propias = await ListRecurringRules(reglas, categorias, MONEDAS, MONEDA).execute(USUARIO)

        # Assert
        assert propias == []


class TestHistorial:
    async def test_devuelve_las_ocurrencias_de_la_regla(
        self,
        reglas: FakeRecurringRuleRepository,
        categorias: FakeCategoryRepository,
        ocurrencias: FakeRecurringOccurrenceRepository,
    ) -> None:
        # Arrange
        regla = _regla_de(reglas)
        await ocurrencias.mark_skipped(regla.id or 0, [date(2026, 6, 10), date(2026, 7, 10)])

        # Act
        historial = await GetRuleOccurrences(
            reglas, categorias, ocurrencias, MONEDAS, MONEDA
        ).execute(USUARIO, regla.id or 0)

        # Assert: de la más reciente a la más vieja.
        assert [o.occurred_on for o in historial] == [date(2026, 7, 10), date(2026, 6, 10)]

    async def test_no_deja_leer_el_historial_de_una_regla_ajena(
        self,
        reglas: FakeRecurringRuleRepository,
        categorias: FakeCategoryRepository,
        ocurrencias: FakeRecurringOccurrenceRepository,
    ) -> None:
        # Arrange
        regla = _regla_de(reglas, user_id=AJENO, category_id=3)
        await ocurrencias.mark_skipped(regla.id or 0, [date(2026, 7, 10)])

        # Act / Assert: sin la verificación de pertenencia, alcanzaría con
        # pasar el id para leer la actividad de otra persona.
        with pytest.raises(ResourceNotFoundError):
            await GetRuleOccurrences(reglas, categorias, ocurrencias, MONEDAS, MONEDA).execute(
                USUARIO, regla.id or 0
            )


class TestProyeccion:
    def _caso(self, reglas: FakeRecurringRuleRepository) -> GetUpcomingOccurrences:
        return GetUpcomingOccurrences(reglas, FixedClock(AHORA), MONEDAS, MONEDA)

    async def test_proyecta_desde_manana(self, reglas: FakeRecurringRuleRepository) -> None:
        # Arrange
        _regla_de(reglas, frecuencia=RecurrenceFrequency.DAILY, day_of_month=None)

        # Act
        resumen = await self._caso(reglas).execute(USUARIO, days=3)

        # Assert: lo de hoy ya lo materializó el job; volver a proyectarlo lo
        # mostraría dos veces.
        assert resumen.date_from == HOY + timedelta(days=1)
        assert [e.due_on for e in resumen.entries] == [
            HOY + timedelta(days=1),
            HOY + timedelta(days=2),
            HOY + timedelta(days=3),
        ]

    async def test_ordena_por_fecha(self, reglas: FakeRecurringRuleRepository) -> None:
        # Arrange
        _regla_de(reglas, day_of_month=20)
        _regla_de(reglas, day_of_month=15)

        # Act
        resumen = await self._caso(reglas).execute(USUARIO, days=30)

        # Assert
        fechas = [e.due_on for e in resumen.entries]
        assert fechas == sorted(fechas)

    async def test_suma_ingresos_y_gastos_por_separado(
        self, reglas: FakeRecurringRuleRepository
    ) -> None:
        # Arrange
        _regla_de(reglas, day_of_month=15, monto="45000.00")
        _regla_de(
            reglas,
            category_id=2,
            tipo=TransactionType.INCOME,
            day_of_month=20,
            monto="850000.00",
        )

        # Act
        resumen = await self._caso(reglas).execute(USUARIO, days=30)

        # Assert
        assert resumen.projected_expense == Money(Decimal("45000.00"), MONEDA)
        assert resumen.projected_income == Money(Decimal("850000.00"), MONEDA)

    async def test_una_regla_pausada_no_proyecta(self, reglas: FakeRecurringRuleRepository) -> None:
        # Arrange
        _regla_de(reglas, is_active=False)

        # Act
        resumen = await self._caso(reglas).execute(USUARIO, days=30)

        # Assert
        assert resumen.entries == []
        assert resumen.projected_expense == Money.zero(MONEDA)

    async def test_no_proyecta_reglas_ajenas(self, reglas: FakeRecurringRuleRepository) -> None:
        # Arrange
        _regla_de(reglas, user_id=AJENO, category_id=3)

        # Act
        resumen = await self._caso(reglas).execute(USUARIO, days=30)

        # Assert
        assert resumen.entries == []

    async def test_rechaza_una_ventana_fuera_de_rango(
        self, reglas: FakeRecurringRuleRepository
    ) -> None:
        # Act / Assert
        with pytest.raises(ValueError, match="days"):
            await self._caso(reglas).execute(USUARIO, days=0)
