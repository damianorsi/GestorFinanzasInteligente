"""Casos de uso de los reportes."""

from __future__ import annotations

from datetime import date

from app.application.dtos import (
    CategoryBreakdown,
    MonthlyTotal,
    MonthlyTrend,
    PeriodSummary,
)
from app.application.exceptions import UnsupportedCurrencyError
from app.application.ports import Clock, ReportRepository
from app.domain.calendar import (
    meses_entre,
    primer_dia_del_mes,
    sumar_meses,
    ultimo_dia_del_mes,
)
from app.domain.enums import TransactionType
from app.domain.value_objects import Money

MESES_POR_DEFECTO_EN_TENDENCIA = 6
MESES_MAXIMOS_EN_TENDENCIA = 36


class _ReportesDelUsuario:
    """Base con la resolución de moneda y período."""

    def __init__(
        self,
        reports: ReportRepository,
        clock: Clock,
        supported_currencies: frozenset[str],
        default_currency: str,
    ) -> None:
        self._reports = reports
        self._clock = clock
        self._supported_currencies = supported_currencies
        self._default_currency = default_currency

    def _resolver_moneda(self, currency: str | None) -> str:
        moneda = (currency or self._default_currency).upper()
        if moneda not in self._supported_currencies:
            habilitadas = ", ".join(sorted(self._supported_currencies))
            raise UnsupportedCurrencyError(
                f"La moneda {moneda} no está habilitada. Disponibles: {habilitadas}."
            )
        return moneda

    def _resolver_periodo(self, date_from: date | None, date_to: date | None) -> tuple[date, date]:
        """Sin período explícito, el mes en curso.

        "Hoy" sale del `Clock`, que resuelve en APP_TIMEZONE: calcularlo en UTC
        haría que entre las 21 y las 24 el reporte mostrara el mes equivocado
        el último día de cada mes.
        """
        hoy = self._clock.today()
        desde = date_from if date_from is not None else primer_dia_del_mes(hoy)
        hasta = date_to if date_to is not None else ultimo_dia_del_mes(hoy)
        if desde > hasta:
            raise ValueError("date_from no puede ser posterior a date_to.")
        return desde, hasta


class GetPeriodSummary(_ReportesDelUsuario):
    async def execute(
        self,
        user_id: int,
        currency: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> PeriodSummary:
        moneda = self._resolver_moneda(currency)
        desde, hasta = self._resolver_periodo(date_from, date_to)
        return await self._reports.period_summary(user_id, moneda, desde, hasta)


class GetCategoryBreakdown(_ReportesDelUsuario):
    async def execute(
        self,
        user_id: int,
        currency: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        type: TransactionType | None = None,
    ) -> CategoryBreakdown:
        moneda = self._resolver_moneda(currency)
        desde, hasta = self._resolver_periodo(date_from, date_to)
        entradas = await self._reports.totals_by_category(user_id, moneda, desde, hasta, type)
        return CategoryBreakdown(currency=moneda, date_from=desde, date_to=hasta, entries=entradas)


class GetMonthlyTrend(_ReportesDelUsuario):
    """Serie mensual de ingresos y gastos.

    Rellena los meses sin movimientos con ceros: un GROUP BY solo devuelve los
    meses que tienen filas, y el gráfico quedaría con agujeros donde en
    realidad hubo actividad nula.
    """

    async def execute(
        self,
        user_id: int,
        currency: str | None = None,
        months: int = MESES_POR_DEFECTO_EN_TENDENCIA,
    ) -> MonthlyTrend:
        moneda = self._resolver_moneda(currency)
        if not 1 <= months <= MESES_MAXIMOS_EN_TENDENCIA:
            raise ValueError(f"months debe estar entre 1 y {MESES_MAXIMOS_EN_TENDENCIA}.")

        hoy = self._clock.today()
        hasta = ultimo_dia_del_mes(hoy)
        # `months` incluye el mes en curso: con months=6 van los cinco anteriores
        # más este, no seis anteriores.
        desde = primer_dia_del_mes(sumar_meses(hoy, -(months - 1)))

        totales = await self._reports.monthly_totals(user_id, moneda, desde, hasta)
        por_periodo = {total.period: total for total in totales}

        cero = Money.zero(moneda)
        entradas = [
            por_periodo.get(periodo, MonthlyTotal(period=periodo, income=cero, expense=cero))
            for periodo in meses_entre(desde, hasta)
        ]
        return MonthlyTrend(currency=moneda, entries=entradas)
