"""Casos de uso del ABM de categorías.

Van los cuatro en un módulo porque comparten la misma resolución de categoría
propia y separarlos obligaría a repetirla o a exportarla de un helper suelto.
"""

from __future__ import annotations

import logging

from app.application.exceptions import (
    DuplicateResourceError,
    ResourceInUseError,
    ResourceNotFoundError,
)
from app.application.ports import CategoryRepository
from app.domain.entities import Category
from app.domain.enums import TransactionType

logger = logging.getLogger(__name__)


class _CategoriasDelUsuario:
    """Base con la resolución de una categoría propia."""

    def __init__(self, categories: CategoryRepository) -> None:
        self._categories = categories

    async def _obtener_propia(self, user_id: int, category_id: int) -> Category:
        categoria = await self._categories.get_for_user(user_id, category_id)
        if categoria is None:
            # 404 y no 403 aunque la categoría exista y sea de otro: un 403
            # confirmaría que ese id está en uso por alguien.
            raise ResourceNotFoundError("La categoría no existe.")
        return categoria

    async def _exigir_nombre_libre(
        self,
        user_id: int,
        name: str,
        type: TransactionType,
        exclude_id: int | None = None,
    ) -> None:
        if await self._categories.exists_with_name(user_id, name, type, exclude_id):
            etiqueta = "ingreso" if type is TransactionType.INCOME else "gasto"
            raise DuplicateResourceError(f"Ya tenés una categoría de {etiqueta} llamada «{name}».")


class ListCategories(_CategoriasDelUsuario):
    async def execute(self, user_id: int, type: TransactionType | None = None) -> list[Category]:
        return await self._categories.list_for_user(user_id, type)


class GetCategory(_CategoriasDelUsuario):
    async def execute(self, user_id: int, category_id: int) -> Category:
        return await self._obtener_propia(user_id, category_id)


class CreateCategory(_CategoriasDelUsuario):
    async def execute(
        self, user_id: int, name: str, type: TransactionType, color: str | None = None
    ) -> Category:
        # La entidad recorta el nombre antes de comprobar la unicidad, para que
        # "Ocio" y " Ocio " no convivan como dos categorías distintas.
        categoria = Category(user_id=user_id, name=name, type=type, color=color)
        await self._exigir_nombre_libre(user_id, categoria.name, type)
        creada = await self._categories.create(categoria)
        logger.info("Categoría creada", extra={"user_id": user_id, "category_id": creada.id})
        return creada


class UpdateCategory(_CategoriasDelUsuario):
    """Edita nombre y color. **El tipo no se puede cambiar.**

    Pasar una categoría de gasto a ingreso convertiría todos sus movimientos
    históricos en lo contrario de lo que se registró, y ni el balance ni los
    reportes tendrían forma de detectarlo. Para cambiar de tipo hay que crear
    otra categoría y mover los movimientos.
    """

    async def execute(
        self,
        user_id: int,
        category_id: int,
        name: str | None = None,
        color: str | None = None,
    ) -> Category:
        categoria = await self._obtener_propia(user_id, category_id)

        if name is not None:
            propuesta = Category(
                user_id=user_id, name=name, type=categoria.type, color=categoria.color
            )
            await self._exigir_nombre_libre(
                user_id, propuesta.name, categoria.type, exclude_id=category_id
            )
            categoria.name = propuesta.name

        if color is not None:
            # Se valida reconstruyendo: la entidad es la que sabe qué color es
            # válido, y duplicar esa regla acá la dejaría desincronizada.
            categoria.color = Category(
                user_id=user_id, name=categoria.name, type=categoria.type, color=color
            ).color

        actualizada = await self._categories.update(categoria)
        logger.info("Categoría actualizada", extra={"user_id": user_id, "category_id": category_id})
        return actualizada


class DeleteCategory(_CategoriasDelUsuario):
    async def execute(self, user_id: int, category_id: int) -> None:
        categoria = await self._obtener_propia(user_id, category_id)

        uso = await self._categories.count_usages(category_id)
        if uso.esta_en_uso:
            raise ResourceInUseError(
                f"No se puede borrar «{categoria.name}»: tiene {uso.describir()} asociados. "
                "Reasignalos o borralos antes."
            )

        await self._categories.delete(user_id, category_id)
        logger.info("Categoría borrada", extra={"user_id": user_id, "category_id": category_id})
