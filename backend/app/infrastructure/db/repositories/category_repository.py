"""Repositorio de categorías sobre SQLAlchemy."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos import CategoryUsage
from app.domain.entities import Category
from app.domain.enums import TransactionType
from app.infrastructure.db.mappers import categoria_a_dominio, categoria_a_modelo
from app.infrastructure.db.models import (
    BudgetModel,
    CategoryModel,
    RecurringRuleModel,
    TransactionModel,
)

# Los ingresos van antes que los gastos, que es como se lee un resumen
# financiero. Explícito para que no dependa del orden del enum.
ORDEN_DE_TIPO = case((CategoryModel.type == TransactionType.INCOME, 0), else_=1)


class SqlAlchemyCategoryRepository:
    """Implementación del puerto `CategoryRepository`.

    Toda consulta lleva `CategoryModel.user_id == user_id` en el WHERE. No hay
    ningún método que devuelva una categoría sin ese filtro.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, categories: Sequence[Category]) -> None:
        self._session.add_all([categoria_a_modelo(categoria) for categoria in categories])
        await self._session.flush()

    async def create(self, category: Category) -> Category:
        modelo = categoria_a_modelo(category)
        self._session.add(modelo)
        await self._session.flush()
        return categoria_a_dominio(modelo)

    async def update(self, category: Category) -> Category:
        if category.id is None:
            raise ValueError("No se puede actualizar una categoría sin id.")
        modelo = await self._session.get(CategoryModel, category.id)
        if modelo is None or modelo.user_id != category.user_id:
            raise ValueError("La categoría no existe o no pertenece al usuario.")
        modelo.name = category.name
        modelo.color = category.color
        await self._session.flush()
        return categoria_a_dominio(modelo)

    async def delete(self, user_id: int, category_id: int) -> None:
        await self._session.execute(
            delete(CategoryModel).where(
                CategoryModel.id == category_id, CategoryModel.user_id == user_id
            )
        )

    async def count_for_user(self, user_id: int) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(CategoryModel).where(CategoryModel.user_id == user_id)
        )
        return int(total or 0)

    async def list_for_user(
        self, user_id: int, type: TransactionType | None = None
    ) -> list[Category]:
        consulta = select(CategoryModel).where(CategoryModel.user_id == user_id)
        if type is not None:
            consulta = consulta.where(CategoryModel.type == type)
        # Orden estable: sin esto la lista del selector del frontend cambiaría
        # de posición entre requests. El criterio del tipo va como CASE
        # explícito y no como `ORDER BY type`, porque MySQL ordena las columnas
        # ENUM por su orden de declaración: reordenar los miembros del enum
        # cambiaría el orden de la API sin que nada lo delate.
        consulta = consulta.order_by(ORDEN_DE_TIPO, CategoryModel.name)
        modelos = (await self._session.scalars(consulta)).all()
        return [categoria_a_dominio(modelo) for modelo in modelos]

    async def get_for_user(self, user_id: int, category_id: int) -> Category | None:
        modelo = await self._session.scalar(
            select(CategoryModel).where(
                CategoryModel.id == category_id, CategoryModel.user_id == user_id
            )
        )
        return categoria_a_dominio(modelo) if modelo is not None else None

    async def exists_with_name(
        self,
        user_id: int,
        name: str,
        type: TransactionType,
        exclude_id: int | None = None,
    ) -> bool:
        consulta = (
            select(func.count())
            .select_from(CategoryModel)
            .where(
                CategoryModel.user_id == user_id,
                CategoryModel.name == name,
                CategoryModel.type == type,
            )
        )
        if exclude_id is not None:
            consulta = consulta.where(CategoryModel.id != exclude_id)
        return bool(await self._session.scalar(consulta))

    async def count_usages(self, category_id: int) -> CategoryUsage:
        async def _contar(modelo: type[TransactionModel | BudgetModel | RecurringRuleModel]) -> int:
            total = await self._session.scalar(
                select(func.count()).select_from(modelo).where(modelo.category_id == category_id)
            )
            return int(total or 0)

        return CategoryUsage(
            transactions=await _contar(TransactionModel),
            budgets=await _contar(BudgetModel),
            recurring_rules=await _contar(RecurringRuleModel),
        )
