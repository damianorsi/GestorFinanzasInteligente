"""Casos de uso del ABM de presupuestos."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from app.application.dtos import BudgetCopyResult, SkippedBudget
from app.application.exceptions import (
    DuplicateResourceError,
    InvalidReferenceError,
    ResourceNotFoundError,
    UnsupportedCurrencyError,
)
from app.application.ports import BudgetRepository, CategoryRepository
from app.domain.entities import Budget, Category
from app.domain.enums import TransactionType
from app.domain.value_objects import Money

logger = logging.getLogger(__name__)


class _PresupuestosDelUsuario:
    """Base con las validaciones compartidas."""

    def __init__(
        self,
        budgets: BudgetRepository,
        categories: CategoryRepository,
        supported_currencies: frozenset[str],
        default_currency: str,
    ) -> None:
        self._budgets = budgets
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

    async def _obtener_propio(self, user_id: int, budget_id: int) -> Budget:
        presupuesto = await self._budgets.get_for_user(user_id, budget_id)
        if presupuesto is None:
            raise ResourceNotFoundError("El presupuesto no existe.")
        return presupuesto

    async def _resolver_categoria_de_gasto(self, user_id: int, category_id: int) -> Category:
        categoria = await self._categories.get_for_user(user_id, category_id)
        if categoria is None:
            raise InvalidReferenceError("La categoría indicada no existe o no es tuya.")
        if categoria.type is not TransactionType.EXPENSE:
            # Presupuestar un ingreso no tiene sentido: un presupuesto es un
            # tope de gasto, y "gastar de menos" en el sueldo no es un desvío.
            raise InvalidReferenceError(
                f"«{categoria.name}» es una categoría de ingreso y los presupuestos "
                "son topes de gasto."
            )
        return categoria


class ListBudgets(_PresupuestosDelUsuario):
    async def execute(
        self, user_id: int, period_month: date, currency: str | None = None
    ) -> list[Budget]:
        moneda = self._resolver_moneda(currency)
        return await self._budgets.list_for_period(user_id, period_month, moneda)


class CreateBudget(_PresupuestosDelUsuario):
    async def execute(
        self,
        user_id: int,
        category_id: int,
        period_month: date,
        amount: Decimal,
        currency: str | None = None,
    ) -> Budget:
        moneda = self._resolver_moneda(currency)
        categoria = await self._resolver_categoria_de_gasto(user_id, category_id)

        if await self._budgets.exists_for(user_id, category_id, period_month, moneda):
            raise DuplicateResourceError(
                f"Ya tenés un presupuesto de «{categoria.name}» para ese mes en {moneda}."
            )

        presupuesto = Budget(
            user_id=user_id,
            category_id=category_id,
            period_month=period_month,
            limit=Money(amount, moneda),
        )
        creado = await self._budgets.create(presupuesto)
        logger.info("Presupuesto creado", extra={"user_id": user_id, "budget_id": creado.id})
        return creado


class UpdateBudget(_PresupuestosDelUsuario):
    """Edita solo el tope.

    La categoría, el período y la moneda son lo que **identifica** al
    presupuesto: cambiarlos no sería editarlo sino crear otro distinto, y
    además podría chocar con uno existente. Para eso está el alta.
    """

    async def execute(self, user_id: int, budget_id: int, amount: Decimal) -> Budget:
        presupuesto = await self._obtener_propio(user_id, budget_id)
        presupuesto.limit = Money(amount, presupuesto.limit.currency)

        # Se reconstruye para revalidar las invariantes sobre el estado final.
        validado = Budget(
            user_id=presupuesto.user_id,
            category_id=presupuesto.category_id,
            period_month=presupuesto.period_month,
            limit=presupuesto.limit,
            id=presupuesto.id,
        )
        actualizado = await self._budgets.update(validado)
        logger.info("Presupuesto actualizado", extra={"user_id": user_id, "budget_id": budget_id})
        return actualizado


class DeleteBudget(_PresupuestosDelUsuario):
    async def execute(self, user_id: int, budget_id: int) -> None:
        await self._obtener_propio(user_id, budget_id)
        await self._budgets.delete(user_id, budget_id)
        logger.info("Presupuesto borrado", extra={"user_id": user_id, "budget_id": budget_id})


class CopyBudgets(_PresupuestosDelUsuario):
    """Copia los presupuestos de un mes a otro.

    Es la operación que hace usable la feature mes a mes: sin esto habría que
    recargar diez topes cada primero de mes.
    """

    async def execute(
        self,
        user_id: int,
        from_period: date,
        to_period: date,
        currency: str | None = None,
    ) -> BudgetCopyResult:
        moneda = self._resolver_moneda(currency)
        if from_period == to_period:
            raise InvalidReferenceError("El período de origen y el de destino son el mismo.")

        origen = await self._budgets.list_for_period(user_id, from_period, moneda)
        destino = await self._budgets.list_for_period(user_id, to_period, moneda)
        ya_presupuestadas = {presupuesto.category_id for presupuesto in destino}

        nombres = {
            categoria.id: categoria.name
            for categoria in await self._categories.list_for_user(user_id)
        }

        a_crear: list[Budget] = []
        salteados: list[SkippedBudget] = []
        for presupuesto in origen:
            if presupuesto.category_id in ya_presupuestadas:
                # No se pisa: sobrescribir destruiría un tope ya ajustado a mano
                # para ese mes.
                salteados.append(
                    SkippedBudget(
                        category_id=presupuesto.category_id,
                        category_name=nombres.get(presupuesto.category_id, "(sin categoría)"),
                    )
                )
                continue
            a_crear.append(
                Budget(
                    user_id=user_id,
                    category_id=presupuesto.category_id,
                    period_month=to_period,
                    limit=presupuesto.limit,
                )
            )

        creados = await self._budgets.create_many(a_crear) if a_crear else 0
        logger.info(
            "Presupuestos copiados",
            extra={"user_id": user_id, "creados": creados, "salteados": len(salteados)},
        )
        return BudgetCopyResult(
            from_period=from_period,
            to_period=to_period,
            currency=moneda,
            created=creados,
            skipped=salteados,
        )
