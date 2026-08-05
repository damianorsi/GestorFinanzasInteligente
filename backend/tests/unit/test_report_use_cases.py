"""Tests de los casos de uso de reportes.

Las agregaciones son SQL y se prueban contra MySQL. Acá se cubre lo que el caso
de uso hace alrededor: resolver el período por defecto, validar la moneda y
rellenar los meses sin movimientos.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.application.dtos import CategoryTotal, MonthlyTotal, PeriodSummary
from app.application.exceptions import UnsupportedCurrencyError
from app.application.use_cases.reports import (
    GetCategoryBreakdown,
    GetMonthlyTrend,
    GetPeriodSummary,
)
from app.domain.enums import TransactionType
from app.domain.value_objects import Money
from tests.fakes import FakeReportRepository, FixedClock

USUARIO = 1
MONEDAS = frozenset({"ARS"})
# 17 de agosto de 2026, 15:00 en Buenos Aires.
AHORA = datetime(2026, 8, 17, 18, 0, tzinfo=UTC)


@pytest.fixture
def reports() -> FakeReportRepository:
    return FakeReportRepository()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(AHORA)


class TestGetPeriodSummary:
    @pytest.fixture
    def caso(self, reports: FakeReportRepository, clock: FixedClock) -> GetPeriodSummary:
        return GetPeriodSummary(reports, clock, MONEDAS, "ARS")

    async def test_sin_periodo_usa_el_mes_en_curso(
        self, caso: GetPeriodSummary, reports: FakeReportRepository
    ) -> None:
        # Arrange / Act
        await caso.execute(USUARIO)

        # Assert
        assert reports.periodos_pedidos == [(date(2026, 8, 1), date(2026, 8, 31))]

    async def test_respeta_el_periodo_explicito(
        self, caso: GetPeriodSummary, reports: FakeReportRepository
    ) -> None:
        # Arrange / Act
        await caso.execute(USUARIO, date_from=date(2026, 1, 1), date_to=date(2026, 3, 31))

        # Assert
        assert reports.periodos_pedidos == [(date(2026, 1, 1), date(2026, 3, 31))]

    async def test_un_periodo_sin_movimientos_devuelve_ceros(self, caso: GetPeriodSummary) -> None:
        """No es un error: un mes sin actividad es una respuesta válida."""
        # Arrange / Act
        resumen = await caso.execute(USUARIO)

        # Assert
        assert resumen.income.is_zero
        assert resumen.expense.is_zero
        assert resumen.balance.is_zero

    async def test_el_balance_puede_ser_negativo(
        self, caso: GetPeriodSummary, reports: FakeReportRepository
    ) -> None:
        # Arrange
        reports.resumen = PeriodSummary(
            currency="ARS",
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
            income=Money.of("100000", "ARS"),
            expense=Money.of("150000", "ARS"),
        )

        # Act
        resumen = await caso.execute(USUARIO)

        # Assert
        assert resumen.balance == Money.of("-50000.00", "ARS")

    async def test_rechaza_una_moneda_no_habilitada(self, caso: GetPeriodSummary) -> None:
        # Arrange / Act / Assert
        with pytest.raises(UnsupportedCurrencyError):
            await caso.execute(USUARIO, currency="USD")

    async def test_rechaza_un_periodo_invertido(self, caso: GetPeriodSummary) -> None:
        # Arrange / Act / Assert
        with pytest.raises(ValueError, match="posterior"):
            await caso.execute(USUARIO, date_from=date(2026, 9, 1), date_to=date(2026, 8, 1))


class TestGetCategoryBreakdown:
    @pytest.fixture
    def caso(self, reports: FakeReportRepository, clock: FixedClock) -> GetCategoryBreakdown:
        return GetCategoryBreakdown(reports, clock, MONEDAS, "ARS")

    async def test_calcula_el_porcentaje_sobre_el_total_de_su_tipo(
        self, caso: GetCategoryBreakdown, reports: FakeReportRepository
    ) -> None:
        """El porcentaje sale del backend para que la torta y cualquier otro
        consumidor usen exactamente el mismo número."""
        # Arrange
        reports.por_categoria = [
            CategoryTotal(1, "Alimentación", TransactionType.EXPENSE, Money.of("750", "ARS"), 3),
            CategoryTotal(2, "Ocio", TransactionType.EXPENSE, Money.of("250", "ARS"), 1),
        ]

        # Act
        desglose = await caso.execute(USUARIO)

        # Assert
        assert desglose.porcentaje_de(desglose.entries[0]) == pytest.approx(75, abs=0.01)
        assert desglose.porcentaje_de(desglose.entries[1]) == pytest.approx(25, abs=0.01)

    async def test_los_porcentajes_se_calculan_por_tipo_por_separado(
        self, caso: GetCategoryBreakdown, reports: FakeReportRepository
    ) -> None:
        """Mezclar ingresos y gastos en un mismo 100% no significaría nada."""
        # Arrange
        reports.por_categoria = [
            CategoryTotal(1, "Sueldo", TransactionType.INCOME, Money.of("1000", "ARS"), 1),
            CategoryTotal(2, "Ocio", TransactionType.EXPENSE, Money.of("400", "ARS"), 2),
        ]

        # Act
        desglose = await caso.execute(USUARIO)

        # Assert
        assert desglose.porcentaje_de(desglose.entries[0]) == pytest.approx(100, abs=0.01)
        assert desglose.porcentaje_de(desglose.entries[1]) == pytest.approx(100, abs=0.01)

    async def test_sin_movimientos_devuelve_una_lista_vacia(
        self, caso: GetCategoryBreakdown
    ) -> None:
        # Arrange / Act
        desglose = await caso.execute(USUARIO)

        # Assert
        assert desglose.entries == []


class TestGetMonthlyTrend:
    @pytest.fixture
    def caso(self, reports: FakeReportRepository, clock: FixedClock) -> GetMonthlyTrend:
        return GetMonthlyTrend(reports, clock, MONEDAS, "ARS")

    async def test_devuelve_una_entrada_por_mes_incluido_el_actual(
        self, caso: GetMonthlyTrend
    ) -> None:
        # Arrange / Act
        tendencia = await caso.execute(USUARIO, months=6)

        # Assert
        assert len(tendencia.entries) == 6
        assert tendencia.entries[-1].period == date(2026, 8, 1)
        assert tendencia.entries[0].period == date(2026, 3, 1)

    async def test_rellena_con_ceros_los_meses_sin_movimientos(
        self, caso: GetMonthlyTrend, reports: FakeReportRepository
    ) -> None:
        """Un GROUP BY no devuelve los meses sin filas y el gráfico quedaría con agujeros."""
        # Arrange
        reports.mensuales = [
            MonthlyTotal(
                period=date(2026, 8, 1),
                income=Money.of("850000", "ARS"),
                expense=Money.of("400000", "ARS"),
            )
        ]

        # Act
        tendencia = await caso.execute(USUARIO, months=3)

        # Assert
        assert [e.period for e in tendencia.entries] == [
            date(2026, 6, 1),
            date(2026, 7, 1),
            date(2026, 8, 1),
        ]
        assert tendencia.entries[0].income.is_zero
        assert tendencia.entries[1].expense.is_zero
        assert tendencia.entries[2].income == Money.of("850000", "ARS")

    async def test_los_meses_vienen_en_orden_cronologico(self, caso: GetMonthlyTrend) -> None:
        # Arrange / Act
        tendencia = await caso.execute(USUARIO, months=12)

        # Assert
        periodos = [e.period for e in tendencia.entries]
        assert periodos == sorted(periodos)

    async def test_una_ventana_que_cruza_el_anio_se_arma_bien(self, caso: GetMonthlyTrend) -> None:
        # Arrange / Act
        tendencia = await caso.execute(USUARIO, months=12)

        # Assert
        assert tendencia.entries[0].period == date(2025, 9, 1)
        assert len(tendencia.entries) == 12

    @pytest.mark.parametrize("months", [0, -1, 37])
    async def test_rechaza_ventanas_fuera_de_rango(
        self, caso: GetMonthlyTrend, months: int
    ) -> None:
        # Arrange / Act / Assert
        with pytest.raises(ValueError, match="months"):
            await caso.execute(USUARIO, months=months)
