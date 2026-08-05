"""Endpoints del CRUD de movimientos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import (
    AppSettings,
    CurrentUser,
    get_create_transaction,
    get_delete_transaction,
    get_export_transactions,
    get_get_transaction,
    get_list_transactions,
    get_update_transaction,
)
from app.api.v1.exporters import FormatoCsv, construir_csv, nombre_de_archivo
from app.api.v1.schemas.transactions import (
    PaginatedTransactions,
    TransactionCreateRequest,
    TransactionResponse,
    TransactionUpdateRequest,
    parsear_sort,
)
from app.application.dtos import LIMITE_MAXIMO, LIMITE_POR_DEFECTO, Page, TransactionFilters
from app.application.use_cases.transactions import (
    CreateTransaction,
    DeleteTransaction,
    ExportTransactions,
    GetTransaction,
    ListTransactions,
    UpdateTransaction,
)
from app.core.errors import ValidationError
from app.domain.enums import TransactionType

router = APIRouter(prefix="/transactions", tags=["transactions"])


def filtros_de_movimientos(
    settings: AppSettings,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    category_id: Annotated[int | None, Query(gt=0)] = None,
    type: Annotated[TransactionType | None, Query()] = None,
    min_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    max_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    q: Annotated[str | None, Query(max_length=255, description="Busca en la descripción.")] = None,
    is_recurring: Annotated[bool | None, Query()] = None,
    sort: Annotated[str | None, Query(description="Ej: `-occurred_on,amount`.")] = None,
) -> TransactionFilters:
    """Arma los filtros a partir de la query string.

    Es una dependencia compartida entre el listado y el export para garantizar
    que el archivo exportado contenga exactamente lo que se ve en pantalla: si
    cada endpoint declarara sus parámetros por separado, alcanzaría con agregar
    un filtro en uno y olvidarlo en el otro.
    """
    try:
        return TransactionFilters(
            currency=(currency or settings.default_currency).upper(),
            date_from=date_from,
            date_to=date_to,
            category_id=category_id,
            type=type,
            min_amount=min_amount,
            max_amount=max_amount,
            q=q,
            is_recurring=is_recurring,
            sort=parsear_sort(sort),
        )
    except ValueError as exc:
        # Coherencias entre filtros (date_from > date_to, min > max) que Pydantic
        # no puede validar campo a campo.
        raise ValidationError(str(exc)) from exc


Filtros = Annotated[TransactionFilters, Depends(filtros_de_movimientos)]


@router.get(
    "",
    response_model=PaginatedTransactions,
    summary="Listar movimientos",
    description=(
        "Paginado y filtrable. `totalCount` cuenta los que cumplen el filtro, no los "
        "devueltos en la página. Los resultados se acotan siempre a una moneda."
    ),
)
async def listar(
    usuario: CurrentUser,
    caso: Annotated[ListTransactions, Depends(get_list_transactions)],
    filtros: Filtros,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=LIMITE_MAXIMO)] = LIMITE_POR_DEFECTO,
) -> PaginatedTransactions:
    resultado = await caso.execute(usuario.id or 0, filtros, Page(offset=offset, limit=limit))
    return PaginatedTransactions(
        entries=[TransactionResponse.desde(m) for m in resultado.entries],
        offset=resultado.offset,
        limit=resultado.limit,
        totalCount=resultado.total_count,
    )


@router.get(
    "/export",
    response_class=Response,
    summary="Exportar movimientos a CSV",
    description=(
        "Respeta exactamente los mismos filtros que el listado. UTF-8 con BOM para que "
        "Excel reconozca los acentos. No incluye proyecciones futuras porque los "
        "movimientos de reglas recurrentes solo se materializan hasta hoy."
    ),
    responses={200: {"content": {"text/csv": {}}}},
)
async def exportar(
    usuario: CurrentUser,
    caso: Annotated[ExportTransactions, Depends(get_export_transactions)],
    filtros: Filtros,
    format: Annotated[
        FormatoCsv,
        Query(
            description=(
                "`standard`: coma como separador y punto decimal. "
                "`excel_es`: punto y coma y coma decimal, que es lo que espera Excel "
                "en español al abrir el archivo con doble clic."
            )
        ),
    ] = FormatoCsv.ESTANDAR,
) -> Response:
    filas = await caso.execute(usuario.id or 0, filtros)
    return Response(
        content=construir_csv(filas, format),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre_de_archivo()}"'},
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Obtener un movimiento",
    description="Un movimiento de otro usuario devuelve 404, no 403.",
)
async def obtener(
    transaction_id: int,
    usuario: CurrentUser,
    caso: Annotated[GetTransaction, Depends(get_get_transaction)],
) -> TransactionResponse:
    return TransactionResponse.desde(await caso.execute(usuario.id or 0, transaction_id))


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TransactionResponse,
    summary="Registrar un movimiento",
    description=(
        "Devuelve 422 si la categoría no es propia, si es de un tipo que no coincide "
        "con el del movimiento, o si la moneda no está habilitada."
    ),
)
async def crear(
    payload: TransactionCreateRequest,
    usuario: CurrentUser,
    caso: Annotated[CreateTransaction, Depends(get_create_transaction)],
    response: Response,
) -> TransactionResponse:
    movimiento = await caso.execute(
        user_id=usuario.id or 0,
        type=payload.type,
        amount=payload.amount,
        occurred_on=payload.occurred_on,
        category_id=payload.category_id,
        description=payload.description,
        currency=payload.currency,
    )
    response.headers["Location"] = f"/api/v1/transactions/{movimiento.id}"
    return TransactionResponse.desde(movimiento)


@router.patch(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Editar un movimiento",
    description="La moneda no es editable.",
)
async def editar(
    transaction_id: int,
    payload: TransactionUpdateRequest,
    usuario: CurrentUser,
    caso: Annotated[UpdateTransaction, Depends(get_update_transaction)],
) -> TransactionResponse:
    movimiento = await caso.execute(
        user_id=usuario.id or 0,
        transaction_id=transaction_id,
        type=payload.type,
        amount=payload.amount,
        occurred_on=payload.occurred_on,
        category_id=payload.category_id,
        description=payload.description,
    )
    return TransactionResponse.desde(movimiento)


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar un movimiento",
    description=(
        "Si lo generó una regla recurrente, su ocurrencia queda marcada como salteada "
        "para que el job no lo vuelva a crear."
    ),
)
async def borrar(
    transaction_id: int,
    usuario: CurrentUser,
    caso: Annotated[DeleteTransaction, Depends(get_delete_transaction)],
) -> None:
    await caso.execute(usuario.id or 0, transaction_id)
