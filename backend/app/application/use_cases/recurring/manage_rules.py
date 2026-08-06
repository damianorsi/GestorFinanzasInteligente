"""Casos de uso del ABM de reglas recurrentes."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from app.application.exceptions import (
    InvalidReferenceError,
    ResourceNotFoundError,
    UnsupportedCurrencyError,
)
from app.application.ports import (
    CategoryRepository,
    Clock,
    RecurringOccurrenceRepository,
    RecurringRuleRepository,
)
from app.domain.entities import Category, RecurringOccurrence, RecurringRule
from app.domain.enums import RecurrenceFrequency, TransactionType
from app.domain.recurrence import fechas_de_la_regla
from app.domain.value_objects import Money

logger = logging.getLogger(__name__)

_ETIQUETA_DE_TIPO = {TransactionType.INCOME: "ingreso", TransactionType.EXPENSE: "gasto"}


class _ReglasDelUsuario:
    """Base con la resolución de moneda, categoría y regla propia."""

    def __init__(
        self,
        rules: RecurringRuleRepository,
        categories: CategoryRepository,
        supported_currencies: frozenset[str],
        default_currency: str,
    ) -> None:
        self._rules = rules
        self._categories = categories
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

    async def _obtener_propia(self, user_id: int, rule_id: int) -> RecurringRule:
        regla = await self._rules.get_for_user(user_id, rule_id)
        if regla is None:
            # 404 aunque exista y sea de otro: un 403 confirmaría el id.
            raise ResourceNotFoundError("La regla no existe.")
        return regla

    async def _resolver_categoria(
        self, user_id: int, category_id: int, tipo: TransactionType
    ) -> Category:
        categoria = await self._categories.get_for_user(user_id, category_id)
        if categoria is None:
            raise InvalidReferenceError("La categoría indicada no existe o no es tuya.")
        if categoria.type is not tipo:
            raise InvalidReferenceError(
                f"La categoría «{categoria.name}» es de {_ETIQUETA_DE_TIPO[categoria.type]} "
                f"y la regla es de {_ETIQUETA_DE_TIPO[tipo]}."
            )
        return categoria


class ListRecurringRules(_ReglasDelUsuario):
    async def execute(
        self, user_id: int, currency: str | None = None, is_active: bool | None = None
    ) -> list[RecurringRule]:
        return await self._rules.list_for_user(user_id, self._resolver_moneda(currency), is_active)


class GetRecurringRule(_ReglasDelUsuario):
    async def execute(self, user_id: int, rule_id: int) -> RecurringRule:
        return await self._obtener_propia(user_id, rule_id)


class CreateRecurringRule(_ReglasDelUsuario):
    async def execute(
        self,
        user_id: int,
        category_id: int,
        type: TransactionType,
        amount: Decimal,
        frequency: RecurrenceFrequency,
        starts_on: date,
        description: str = "",
        day_of_month: int | None = None,
        day_of_week: int | None = None,
        ends_on: date | None = None,
        currency: str | None = None,
    ) -> RecurringRule:
        moneda = self._resolver_moneda(currency)
        await self._resolver_categoria(user_id, category_id, type)

        regla = RecurringRule(
            user_id=user_id,
            category_id=category_id,
            type=type,
            money=Money(amount, moneda),
            frequency=frequency,
            starts_on=starts_on,
            description=description,
            day_of_month=day_of_month,
            day_of_week=day_of_week,
            ends_on=ends_on,
        )
        creada = await self._rules.create(regla)
        logger.info("Regla recurrente creada", extra={"user_id": user_id, "rule_id": creada.id})
        return creada


class UpdateRecurringRule(_ReglasDelUsuario):
    """Edita una regla existente.

    Cambiar el monto afecta **solo a las ocurrencias futuras**: las ya
    generadas son movimientos reales y no se tocan. Reescribirlas cambiaría el
    historial de gastos de meses ya cerrados (docs/PROMPT.md §9).
    """

    def __init__(
        self,
        rules: RecurringRuleRepository,
        categories: CategoryRepository,
        occurrences: RecurringOccurrenceRepository,
        clock: Clock,
        supported_currencies: frozenset[str],
        default_currency: str,
        catchup_max_days: int,
    ) -> None:
        super().__init__(rules, categories, supported_currencies, default_currency)
        self._occurrences = occurrences
        self._clock = clock
        self._catchup_max_days = catchup_max_days

    async def execute(
        self,
        user_id: int,
        rule_id: int,
        *,
        category_id: int | None = None,
        amount: Decimal | None = None,
        frequency: RecurrenceFrequency | None = None,
        starts_on: date | None = None,
        description: str | None = None,
        day_of_month: int | None = None,
        day_of_week: int | None = None,
        ends_on: date | None = None,
        is_active: bool | None = None,
        limpiar_ends_on: bool = False,
        limpiar_day_of_month: bool = False,
        limpiar_day_of_week: bool = False,
    ) -> RecurringRule:
        actual = await self._obtener_propia(user_id, rule_id)

        nueva_frecuencia = frequency or actual.frequency
        nueva_categoria = category_id if category_id is not None else actual.category_id
        if category_id is not None:
            await self._resolver_categoria(user_id, nueva_categoria, actual.type)

        # Los parámetros de día se recalculan según la frecuencia final: cada
        # frecuencia exige exactamente los suyos y rechaza los sobrantes, así
        # que arrastrar el `day_of_month` de una regla que pasó a semanal la
        # dejaría inválida.
        dia_del_mes = self._resolver_dia(
            explicito=day_of_month,
            actual=actual.day_of_month,
            limpiar=limpiar_day_of_month,
            aplica=nueva_frecuencia is RecurrenceFrequency.MONTHLY,
        )
        dia_de_la_semana = self._resolver_dia(
            explicito=day_of_week,
            actual=actual.day_of_week,
            limpiar=limpiar_day_of_week,
            aplica=nueva_frecuencia is RecurrenceFrequency.WEEKLY,
        )

        # Se reconstruye entera para que la entidad revalide las invariantes
        # sobre el estado final, no sobre el parcial.
        actualizada = RecurringRule(
            id=actual.id,
            user_id=actual.user_id,
            category_id=nueva_categoria,
            type=actual.type,
            money=Money(amount, actual.money.currency) if amount is not None else actual.money,
            frequency=nueva_frecuencia,
            starts_on=starts_on or actual.starts_on,
            description=actual.description if description is None else description,
            day_of_month=dia_del_mes,
            day_of_week=dia_de_la_semana,
            ends_on=None if limpiar_ends_on else (ends_on or actual.ends_on),
            is_active=actual.is_active if is_active is None else is_active,
        )

        reactivada = not actual.is_active and actualizada.is_active
        guardada = await self._rules.update(actualizada)

        if reactivada:
            await self._cerrar_el_periodo_de_pausa(guardada)

        logger.info(
            "Regla recurrente actualizada",
            extra={"user_id": user_id, "rule_id": rule_id, "is_active": guardada.is_active},
        )
        return guardada

    async def _cerrar_el_periodo_de_pausa(self, regla: RecurringRule) -> None:
        """Da por resueltas las fechas que la regla no generó mientras estuvo pausada.

        Sin esto, reactivar una regla pausada tres meses haría que el job
        inyecte tres meses de movimientos que nunca ocurrieron: el libro mayor
        no tiene esas fechas y el job las trata como pendientes. Pausar es
        decidir no generar, no diferir (docs/PROMPT.md §9).

        Se acota a la ventana de catch-up porque más atrás el job no miraría de
        todos modos.
        """
        hoy = self._clock.today()
        desde = max(regla.starts_on, hoy - timedelta(days=self._catchup_max_days))
        pendientes = fechas_de_la_regla(regla, desde, hoy)
        if not pendientes:
            return

        anotadas = await self._occurrences.mark_skipped(regla.id or 0, pendientes)
        logger.info(
            "Período de pausa cerrado al reactivar la regla",
            extra={"rule_id": regla.id, "salteadas": anotadas},
        )

    @staticmethod
    def _resolver_dia(
        *, explicito: int | None, actual: int | None, limpiar: bool, aplica: bool
    ) -> int | None:
        if not aplica:
            return None
        if limpiar:
            return None
        return explicito if explicito is not None else actual


class DeleteRecurringRule(_ReglasDelUsuario):
    """Borra la regla sin tocar los movimientos ya generados.

    Quedan como movimientos sueltos con `recurring_rule_id = NULL`. Borrarlos
    sería reescribir el historial: la persona los pagó igual.
    """

    async def execute(self, user_id: int, rule_id: int) -> None:
        await self._obtener_propia(user_id, rule_id)
        await self._rules.delete(user_id, rule_id)
        logger.info("Regla recurrente borrada", extra={"user_id": user_id, "rule_id": rule_id})


class GetRuleOccurrences(_ReglasDelUsuario):
    """Historial de lo que la regla generó y de lo que se salteó."""

    def __init__(
        self,
        rules: RecurringRuleRepository,
        categories: CategoryRepository,
        occurrences: RecurringOccurrenceRepository,
        supported_currencies: frozenset[str],
        default_currency: str,
    ) -> None:
        super().__init__(rules, categories, supported_currencies, default_currency)
        self._occurrences = occurrences

    async def execute(self, user_id: int, rule_id: int) -> list[RecurringOccurrence]:
        # Se resuelve la regla primero: sin esto, cualquiera podría leer el
        # historial de una regla ajena pasando su id.
        await self._obtener_propia(user_id, rule_id)
        return await self._occurrences.list_for_rule(rule_id)
