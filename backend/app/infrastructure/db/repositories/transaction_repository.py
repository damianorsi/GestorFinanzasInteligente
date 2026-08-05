"""Repositorio de movimientos sobre SQLAlchemy."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos import (
    Page,
    PaginatedResult,
    SortCriterion,
    SortDirection,
    SortField,
    TransactionFilters,
)
from app.domain.entities import Transaction
from app.infrastructure.db.mappers import movimiento_a_dominio, movimiento_a_modelo
from app.infrastructure.db.models import TransactionModel

_COLUMNAS_ORDENABLES = {
    SortField.OCCURRED_ON: TransactionModel.occurred_on,
    SortField.AMOUNT: TransactionModel.amount,
    SortField.CREATED_AT: TransactionModel.created_at,
    SortField.DESCRIPTION: TransactionModel.description,
}


class SqlAlchemyTransactionRepository:
    """Implementación del puerto `TransactionRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, transaction: Transaction) -> Transaction:
        modelo = movimiento_a_modelo(transaction)
        self._session.add(modelo)
        await self._session.flush()
        return movimiento_a_dominio(modelo)

    async def update(self, transaction: Transaction) -> Transaction:
        if transaction.id is None:
            raise ValueError("No se puede actualizar un movimiento sin id.")
        modelo = await self._session.get(TransactionModel, transaction.id)
        if modelo is None or modelo.user_id != transaction.user_id:
            raise ValueError("El movimiento no existe o no pertenece al usuario.")
        modelo.category_id = transaction.category_id
        modelo.type = transaction.type
        modelo.amount = transaction.money.amount
        modelo.currency = transaction.money.currency
        modelo.occurred_on = transaction.occurred_on
        modelo.description = transaction.description
        await self._session.flush()
        return movimiento_a_dominio(modelo)

    async def delete(self, user_id: int, transaction_id: int) -> None:
        await self._session.execute(
            delete(TransactionModel).where(
                TransactionModel.id == transaction_id, TransactionModel.user_id == user_id
            )
        )

    async def get_for_user(self, user_id: int, transaction_id: int) -> Transaction | None:
        modelo = await self._session.scalar(
            select(TransactionModel).where(
                TransactionModel.id == transaction_id, TransactionModel.user_id == user_id
            )
        )
        return movimiento_a_dominio(modelo) if modelo is not None else None

    async def search(
        self, user_id: int, filters: TransactionFilters, page: Page
    ) -> PaginatedResult[Transaction]:
        total = await self._session.scalar(
            self._filtrar(select(func.count()).select_from(TransactionModel), user_id, filters)
        )

        consulta = (
            self._filtrar(select(TransactionModel), user_id, filters)
            .order_by(*self._ordenar(filters.sort))
            .offset(page.offset)
            .limit(page.limit)
        )
        modelos = (await self._session.scalars(consulta)).all()

        return PaginatedResult(
            entries=[movimiento_a_dominio(modelo) for modelo in modelos],
            offset=page.offset,
            limit=page.limit,
            total_count=int(total or 0),
        )

    def _filtrar(
        self, consulta: Select[Any], user_id: int, filters: TransactionFilters
    ) -> Select[Any]:
        # `user_id` y `currency` van siempre: sumar montos de monedas distintas
        # daría un total sin significado (docs/PROMPT.md §5.1).
        consulta = consulta.where(
            TransactionModel.user_id == user_id,
            TransactionModel.currency == filters.currency,
        )

        if filters.date_from is not None:
            consulta = consulta.where(TransactionModel.occurred_on >= filters.date_from)
        if filters.date_to is not None:
            consulta = consulta.where(TransactionModel.occurred_on <= filters.date_to)
        if filters.category_id is not None:
            consulta = consulta.where(TransactionModel.category_id == filters.category_id)
        if filters.type is not None:
            consulta = consulta.where(TransactionModel.type == filters.type)
        if filters.min_amount is not None:
            consulta = consulta.where(TransactionModel.amount >= filters.min_amount)
        if filters.max_amount is not None:
            consulta = consulta.where(TransactionModel.amount <= filters.max_amount)
        if filters.q:
            # `autoescape=True` es imprescindible: sin eso, buscar "%" o "_"
            # los pasaría como comodines de LIKE y devolvería todo.
            consulta = consulta.where(
                TransactionModel.description.contains(filters.q, autoescape=True)
            )
        if filters.is_recurring is True:
            consulta = consulta.where(TransactionModel.recurring_rule_id.is_not(None))
        elif filters.is_recurring is False:
            consulta = consulta.where(TransactionModel.recurring_rule_id.is_(None))

        return consulta

    def _ordenar(self, criterios: tuple[SortCriterion, ...]) -> list[Any]:
        orden: list[Any] = []
        for criterio in criterios:
            columna = _COLUMNAS_ORDENABLES[criterio.field]
            orden.append(
                columna.desc() if criterio.direction is SortDirection.DESC else columna.asc()
            )
        # Desempate por id, siempre. Sin una clave única al final, dos filas con
        # la misma fecha pueden salir en distinto orden entre consultas y la
        # paginación repetiría una y se saltearía otra.
        orden.append(TransactionModel.id.desc())
        return orden
