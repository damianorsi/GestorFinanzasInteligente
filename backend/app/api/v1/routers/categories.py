"""Endpoints del ABM de categorías."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import (
    CurrentUser,
    get_create_category,
    get_delete_category,
    get_get_category,
    get_list_categories,
    get_update_category,
)
from app.api.v1.schemas.categories import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
)
from app.application.use_cases.categories import (
    CreateCategory,
    DeleteCategory,
    GetCategory,
    ListCategories,
    UpdateCategory,
)
from app.domain.entities import Category
from app.domain.enums import TransactionType

router = APIRouter(prefix="/categories", tags=["categories"])


def _a_respuesta(categoria: Category) -> CategoryResponse:
    return CategoryResponse(
        id=categoria.id or 0,
        name=categoria.name,
        type=categoria.type,
        color=categoria.color,
        is_default=categoria.is_default,
    )


@router.get(
    "",
    response_model=list[CategoryResponse],
    summary="Listar las categorías propias",
    description=(
        "Devuelve el listado completo, sin paginar: la colección está acotada por "
        "usuario y el frontend la necesita entera para poblar los selectores."
    ),
)
async def listar(
    usuario: CurrentUser,
    caso: Annotated[ListCategories, Depends(get_list_categories)],
    type: Annotated[TransactionType | None, Query(description="Filtra por tipo.")] = None,
) -> list[CategoryResponse]:
    categorias = await caso.execute(user_id=usuario.id or 0, type=type)
    return [_a_respuesta(categoria) for categoria in categorias]


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Obtener una categoría",
    description="Una categoría de otro usuario devuelve 404, no 403.",
)
async def obtener(
    category_id: int,
    usuario: CurrentUser,
    caso: Annotated[GetCategory, Depends(get_get_category)],
) -> CategoryResponse:
    return _a_respuesta(await caso.execute(user_id=usuario.id or 0, category_id=category_id))


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CategoryResponse,
    summary="Crear una categoría",
    description="Devuelve 409 si ya existe otra con el mismo nombre y tipo.",
)
async def crear(
    payload: CategoryCreateRequest,
    usuario: CurrentUser,
    caso: Annotated[CreateCategory, Depends(get_create_category)],
    response: Response,
) -> CategoryResponse:
    categoria = await caso.execute(
        user_id=usuario.id or 0,
        name=payload.name,
        type=payload.type,
        color=payload.color,
    )
    response.headers["Location"] = f"/api/v1/categories/{categoria.id}"
    return _a_respuesta(categoria)


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Editar una categoría",
    description="Solo nombre y color; el tipo es inmutable.",
)
async def editar(
    category_id: int,
    payload: CategoryUpdateRequest,
    usuario: CurrentUser,
    caso: Annotated[UpdateCategory, Depends(get_update_category)],
) -> CategoryResponse:
    categoria = await caso.execute(
        user_id=usuario.id or 0,
        category_id=category_id,
        name=payload.name,
        color=payload.color,
    )
    return _a_respuesta(categoria)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar una categoría",
    description=(
        "Devuelve 409 si tiene movimientos, presupuestos o reglas asociados, "
        "enumerando en el mensaje qué está bloqueando el borrado."
    ),
)
async def borrar(
    category_id: int,
    usuario: CurrentUser,
    caso: Annotated[DeleteCategory, Depends(get_delete_category)],
) -> None:
    await caso.execute(user_id=usuario.id or 0, category_id=category_id)
