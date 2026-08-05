"""Casos de uso del CRUD de movimientos."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from app.application.dtos import Page, PaginatedResult, TransactionFilters
from app.application.exceptions import (
    InvalidReferenceError,
    ResourceNotFoundError,
    UnsupportedCurrencyError,
)
from app.application.ports import (
    CategoryRepository,
    RecurringOccurrenceRepository,
    TransactionRepository,
)
from app.domain.entities import Category, Transaction
from app.domain.enums import TransactionType
from app.domain.value_objects import Money

logger = logging.getLogger(__name__)

_ETIQUETA_DE_TIPO = {TransactionType.INCOME: "ingreso", TransactionType.EXPENSE: "gasto"}


class _MovimientosDelUsuario:
    """Base con la resolución de un movimiento propio."""

    def __init__(self, transactions: TransactionRepository) -> None:
        self._transactions = transactions

    async def _obtener_propio(self, user_id: int, transaction_id: int) -> Transaction:
        movimiento = await self._transactions.get_for_user(user_id, transaction_id)
        if movimiento is None:
            # 404 aunque exista y sea de otro: un 403 confirmaría el id.
            raise ResourceNotFoundError("El movimiento no existe.")
        return movimiento


class _ValidaReferencias:
    """Comprobaciones compartidas por el alta y la edición."""

    def __init__(
        self,
        categories: CategoryRepository,
        supported_currencies: frozenset[str],
        default_currency: str,
    ) -> None:
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

    async def _resolver_categoria(
        self, user_id: int, category_id: int, tipo: TransactionType
    ) -> Category:
        categoria = await self._categories.get_for_user(user_id, category_id)
        if categoria is None:
            # 422 y no 404: el recurso pedido no es la categoría sino el
            # movimiento; lo que está mal es un dato del cuerpo del request.
            raise InvalidReferenceError("La categoría indicada no existe o no es tuya.")
        if categoria.type is not tipo:
            raise InvalidReferenceError(
                f"La categoría «{categoria.name}» es de {_ETIQUETA_DE_TIPO[categoria.type]} "
                f"y el movimiento es de {_ETIQUETA_DE_TIPO[tipo]}."
            )
        return categoria


class ListTransactions(_MovimientosDelUsuario):
    async def execute(
        self, user_id: int, filters: TransactionFilters, page: Page
    ) -> PaginatedResult[Transaction]:
        return await self._transactions.search(user_id, filters, page)


class GetTransaction(_MovimientosDelUsuario):
    async def execute(self, user_id: int, transaction_id: int) -> Transaction:
        return await self._obtener_propio(user_id, transaction_id)


class CreateTransaction(_MovimientosDelUsuario, _ValidaReferencias):
    def __init__(
        self,
        transactions: TransactionRepository,
        categories: CategoryRepository,
        supported_currencies: frozenset[str],
        default_currency: str,
    ) -> None:
        _MovimientosDelUsuario.__init__(self, transactions)
        _ValidaReferencias.__init__(self, categories, supported_currencies, default_currency)

    async def execute(
        self,
        user_id: int,
        type: TransactionType,
        amount: Decimal,
        occurred_on: date,
        category_id: int,
        description: str = "",
        currency: str | None = None,
    ) -> Transaction:
        moneda = self._resolver_moneda(currency)
        await self._resolver_categoria(user_id, category_id, type)

        movimiento = Transaction(
            user_id=user_id,
            category_id=category_id,
            type=type,
            money=Money(amount, moneda),
            occurred_on=occurred_on,
            description=description,
        )
        creado = await self._transactions.create(movimiento)
        logger.info(
            "Movimiento creado",
            extra={"user_id": user_id, "transaction_id": creado.id, "type": type.value},
        )
        return creado


class UpdateTransaction(_MovimientosDelUsuario, _ValidaReferencias):
    """Edita un movimiento existente.

    La moneda no se puede cambiar: en v1 hay una sola, y cuando haya más,
    "cambiar de moneda" no es editar un campo sino convertir un importe, que
    necesita una cotización y una política que todavía no existen.
    """

    def __init__(
        self,
        transactions: TransactionRepository,
        categories: CategoryRepository,
        supported_currencies: frozenset[str],
        default_currency: str,
    ) -> None:
        _MovimientosDelUsuario.__init__(self, transactions)
        _ValidaReferencias.__init__(self, categories, supported_currencies, default_currency)

    async def execute(
        self,
        user_id: int,
        transaction_id: int,
        type: TransactionType | None = None,
        amount: Decimal | None = None,
        occurred_on: date | None = None,
        category_id: int | None = None,
        description: str | None = None,
    ) -> Transaction:
        movimiento = await self._obtener_propio(user_id, transaction_id)

        tipo_final = type if type is not None else movimiento.type
        categoria_final = category_id if category_id is not None else movimiento.category_id

        # Se revalida aunque solo haya cambiado el tipo: la categoría que servía
        # para un gasto no sirve para un ingreso.
        if type is not None or category_id is not None:
            await self._resolver_categoria(user_id, categoria_final, tipo_final)

        movimiento.type = tipo_final
        movimiento.category_id = categoria_final
        if amount is not None:
            movimiento.money = Money(amount, movimiento.money.currency)
        if occurred_on is not None:
            movimiento.occurred_on = occurred_on
        if description is not None:
            movimiento.description = description

        # Se reconstruye para que las invariantes de la entidad —monto positivo,
        # largo de la descripción— se validen sobre el estado final y no solo al
        # crearla.
        validado = Transaction(
            user_id=movimiento.user_id,
            category_id=movimiento.category_id,
            type=movimiento.type,
            money=movimiento.money,
            occurred_on=movimiento.occurred_on,
            description=movimiento.description,
            id=movimiento.id,
            recurring_rule_id=movimiento.recurring_rule_id,
        )

        actualizado = await self._transactions.update(validado)
        logger.info(
            "Movimiento actualizado",
            extra={"user_id": user_id, "transaction_id": transaction_id},
        )
        return actualizado


class DeleteTransaction(_MovimientosDelUsuario):
    """Borra un movimiento.

    Si lo había generado una regla recurrente, marca su ocurrencia como
    salteada. Sin eso, el job la volvería a generar en la corrida siguiente y
    el movimiento que se borró a propósito reaparecería al otro día.
    """

    def __init__(
        self,
        transactions: TransactionRepository,
        occurrences: RecurringOccurrenceRepository,
    ) -> None:
        super().__init__(transactions)
        self._occurrences = occurrences

    async def execute(self, user_id: int, transaction_id: int) -> None:
        movimiento = await self._obtener_propio(user_id, transaction_id)

        if movimiento.is_recurring:
            await self._occurrences.mark_skipped_by_transaction(transaction_id)

        await self._transactions.delete(user_id, transaction_id)
        logger.info(
            "Movimiento borrado",
            extra={
                "user_id": user_id,
                "transaction_id": transaction_id,
                "era_recurrente": movimiento.is_recurring,
            },
        )
