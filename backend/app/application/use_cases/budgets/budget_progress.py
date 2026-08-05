"""Caso de uso: avance de los presupuestos de un mes."""

from __future__ import annotations

from datetime import date

from app.application.dtos import (
    BudgetProgress,
    BudgetProgressReport,
    UnbudgetedSpending,
)
from app.application.exceptions import UnsupportedCurrencyError
from app.application.ports import BudgetRepository, CategoryRepository, ReportRepository
from app.domain.budgets import evaluar_estado, porcentaje_gastado, restante
from app.domain.calendar import primer_dia_del_mes, ultimo_dia_del_mes
from app.domain.enums import TransactionType
from app.domain.value_objects import Money

CATEGORIA_DESCONOCIDA = "(sin categoría)"


class GetBudgetProgress:
    """Cruza los topes del mes con lo efectivamente gastado.

    El gasto sale de la misma agregación que usan los reportes, no de una
    consulta propia: si fueran dos, el número del presupuesto y el del reporte
    podrían discrepar y no habría forma de saber cuál está mal.

    Solo cuenta movimientos **reales**: las reglas recurrentes se materializan
    hasta hoy, así que las proyecciones futuras no inflan el gasto del mes.
    """

    def __init__(
        self,
        budgets: BudgetRepository,
        categories: CategoryRepository,
        reports: ReportRepository,
        supported_currencies: frozenset[str],
        default_currency: str,
    ) -> None:
        self._budgets = budgets
        self._categories = categories
        self._reports = reports
        self._supported_currencies = supported_currencies
        self._default_currency = default_currency

    async def execute(
        self, user_id: int, period_month: date, currency: str | None = None
    ) -> BudgetProgressReport:
        moneda = (currency or self._default_currency).upper()
        if moneda not in self._supported_currencies:
            habilitadas = ", ".join(sorted(self._supported_currencies))
            raise UnsupportedCurrencyError(
                f"La moneda {moneda} no está habilitada. Disponibles: {habilitadas}."
            )

        desde = primer_dia_del_mes(period_month)
        hasta = ultimo_dia_del_mes(period_month)

        presupuestos = await self._budgets.list_for_period(user_id, desde, moneda)
        gastos = await self._reports.totals_by_category(
            user_id, moneda, desde, hasta, TransactionType.EXPENSE
        )
        gasto_por_categoria = {gasto.category_id: gasto for gasto in gastos}
        nombres = {
            categoria.id: categoria.name
            for categoria in await self._categories.list_for_user(user_id)
        }

        cero = Money.zero(moneda)
        entradas = []
        for presupuesto in presupuestos:
            gasto = gasto_por_categoria.get(presupuesto.category_id)
            gastado = gasto.total if gasto is not None else cero
            entradas.append(
                BudgetProgress(
                    budget_id=presupuesto.id or 0,
                    category_id=presupuesto.category_id,
                    category_name=nombres.get(presupuesto.category_id, CATEGORIA_DESCONOCIDA),
                    budgeted=presupuesto.limit,
                    spent=gastado,
                    remaining=restante(gastado, presupuesto.limit),
                    percentage=porcentaje_gastado(gastado, presupuesto.limit),
                    status=evaluar_estado(gastado, presupuesto.limit),
                )
            )

        # Lo más comprometido primero: es lo que hay que mirar.
        entradas.sort(key=lambda entrada: entrada.percentage, reverse=True)

        con_presupuesto = {presupuesto.category_id for presupuesto in presupuestos}
        sin_presupuestar = [
            UnbudgetedSpending(
                category_id=gasto.category_id,
                category_name=gasto.category_name,
                spent=gasto.total,
            )
            for gasto in gastos
            if gasto.category_id not in con_presupuesto
        ]

        return BudgetProgressReport(
            currency=moneda,
            period_month=desde,
            entries=entradas,
            unbudgeted=sin_presupuestar,
        )
