"""Vencimientos proyectados de las reglas recurrentes."""

from __future__ import annotations

from datetime import timedelta

from app.application.dtos import UpcomingOccurrence, UpcomingSummary
from app.application.exceptions import UnsupportedCurrencyError
from app.application.ports import Clock, RecurringRuleRepository
from app.domain.enums import TransactionType
from app.domain.recurrence import fechas_proyectadas_hasta
from app.domain.value_objects import Money

DIAS_POR_DEFECTO = 30
DIAS_MAXIMOS = 365


class GetUpcomingOccurrences:
    """Qué va a generar cada regla en los próximos días.

    **Es una proyección y nada más.** Estas fechas no existen como movimientos:
    no entran en el balance, ni en los reportes, ni en el export CSV. Si
    entraran, el balance de hoy mostraría plata que todavía no se movió
    (docs/PROMPT.md §9).
    """

    def __init__(
        self,
        rules: RecurringRuleRepository,
        clock: Clock,
        supported_currencies: frozenset[str],
        default_currency: str,
    ) -> None:
        self._rules = rules
        self._clock = clock
        self._supported_currencies = supported_currencies
        self._default_currency = default_currency

    async def execute(
        self, user_id: int, days: int = DIAS_POR_DEFECTO, currency: str | None = None
    ) -> UpcomingSummary:
        moneda = (currency or self._default_currency).upper()
        if moneda not in self._supported_currencies:
            habilitadas = ", ".join(sorted(self._supported_currencies))
            raise UnsupportedCurrencyError(
                f"La moneda {moneda} no está habilitada. Disponibles: {habilitadas}."
            )
        if not 1 <= days <= DIAS_MAXIMOS:
            raise ValueError(f"days debe estar entre 1 y {DIAS_MAXIMOS}.")

        # Desde mañana: lo de hoy ya lo materializó el job, y volver a
        # proyectarlo lo mostraría dos veces.
        desde = self._clock.today() + timedelta(days=1)
        hasta = self._clock.today() + timedelta(days=days)

        reglas = await self._rules.list_active_for_user(user_id, moneda)
        entradas: list[UpcomingOccurrence] = []
        for regla in reglas:
            entradas.extend(
                UpcomingOccurrence(
                    rule_id=regla.id or 0,
                    category_id=regla.category_id,
                    description=regla.description,
                    money=regla.money,
                    due_on=fecha,
                    type_is_income=regla.type is TransactionType.INCOME,
                )
                for fecha in fechas_proyectadas_hasta(regla, desde, hasta)
            )

        entradas.sort(key=lambda entrada: (entrada.due_on, entrada.rule_id))

        ingresos = Money.sum(
            (entrada.money for entrada in entradas if entrada.type_is_income), moneda
        )
        gastos = Money.sum(
            (entrada.money for entrada in entradas if not entrada.type_is_income), moneda
        )

        return UpcomingSummary(
            date_from=desde,
            date_to=hasta,
            currency=moneda,
            entries=entradas,
            projected_income=ingresos,
            projected_expense=gastos,
        )
