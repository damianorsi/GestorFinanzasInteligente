"""Schemas de request y response de metas de ahorro (docs/PROMPT.md §21.3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.application.dtos import SavingsGoalProgress, SavingsProjection
from app.domain.entities import SavingsGoal
from app.domain.enums import GoalStatus

_CONFIG_REQUEST = ConfigDict(extra="forbid")

PRECISION_MONTO = 14
DECIMALES_MONTO = 2
LARGO_MAXIMO_DEL_NOMBRE = 120


class SavingsGoalResponse(BaseModel):
    id: int
    name: str
    target_amount: str
    currency: str
    starts_on: date
    target_date: date | None
    is_active: bool

    @classmethod
    def desde(cls, meta: SavingsGoal) -> SavingsGoalResponse:
        return cls(
            id=meta.id or 0,
            name=meta.name,
            target_amount=str(meta.target.amount),
            currency=meta.target.currency,
            starts_on=meta.starts_on,
            target_date=meta.target_date,
            is_active=meta.is_active,
        )


class SavingsProjectionResponse(BaseModel):
    """La parte estimada, separada de la medida.

    Viaja anidada y no aplanada para que el cliente no pueda mostrar una fecha
    estimada sin tener a mano sobre cuántos meses se calculó.
    """

    monthly_rate: str
    months_of_history: int
    # Null cuando a ese ritmo no se llega nunca, o cuando el horizonte es tan
    # largo que informarlo no ayudaría.
    months_to_target: int | None
    projected_date: date | None

    @classmethod
    def desde(cls, proyeccion: SavingsProjection) -> SavingsProjectionResponse:
        return cls(
            monthly_rate=str(proyeccion.monthly_rate.amount),
            months_of_history=proyeccion.months_of_history,
            months_to_target=proyeccion.months_to_target,
            projected_date=proyeccion.projected_date,
        )


class SavingsGoalProgressResponse(BaseModel):
    goal_id: int
    name: str
    target: str
    saved: str
    remaining: str
    percentage: str
    currency: str
    starts_on: date
    target_date: date | None
    # Null cuando no hay historial con qué decidir: forzar uno de los tres
    # estados convertiría una falta de datos en un diagnóstico.
    status: GoalStatus | None
    # Null cuando faltan datos. El cliente dice que faltan en vez de proyectar.
    projection: SavingsProjectionResponse | None

    @classmethod
    def desde(cls, avance: SavingsGoalProgress) -> SavingsGoalProgressResponse:
        return cls(
            goal_id=avance.goal_id,
            name=avance.name,
            target=str(avance.target.amount),
            saved=str(avance.saved.amount),
            remaining=str(avance.remaining.amount),
            percentage=str(avance.percentage),
            currency=avance.target.currency,
            starts_on=avance.starts_on,
            target_date=avance.target_date,
            status=avance.status,
            projection=(
                None
                if avance.projection is None
                else SavingsProjectionResponse.desde(avance.projection)
            ),
        )


class SavingsGoalCreateRequest(BaseModel):
    model_config = _CONFIG_REQUEST

    name: str = Field(min_length=1, max_length=LARGO_MAXIMO_DEL_NOMBRE)
    target_amount: Decimal = Field(gt=0, max_digits=PRECISION_MONTO, decimal_places=DECIMALES_MONTO)
    # Sin fecha de inicio la meta arranca hoy: contar un balance ya gastado
    # inflaría el avance desde el minuto cero.
    starts_on: date | None = None
    target_date: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class SavingsGoalUpdateRequest(BaseModel):
    """Todo opcional: es un PATCH.

    `clear_target_date` existe porque `target_date: null` ya significa «no lo
    toques». Sin un flag aparte, una meta con fecha no podría volver a no
    tenerla — el mismo problema que resuelve `clear_ends_on` en las reglas
    recurrentes.
    """

    model_config = _CONFIG_REQUEST

    name: str | None = Field(default=None, min_length=1, max_length=LARGO_MAXIMO_DEL_NOMBRE)
    target_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=PRECISION_MONTO, decimal_places=DECIMALES_MONTO
    )
    starts_on: date | None = None
    target_date: date | None = None
    is_active: bool | None = None
    clear_target_date: bool = False
