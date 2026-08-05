"""Schemas de request y response de categorías."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import TransactionType

PATRON_COLOR = r"^#[0-9a-fA-F]{6}$"


# `extra="forbid"` en los requests: un campo desconocido devuelve 422 en vez de
# ignorarse en silencio. Sin esto, mandar `type` en un PATCH parecería funcionar
# y no cambiaría nada, que es peor que un error claro.
_CONFIG_REQUEST = ConfigDict(extra="forbid")


class CategoryCreateRequest(BaseModel):
    model_config = _CONFIG_REQUEST

    name: str = Field(min_length=1, max_length=60)
    type: TransactionType
    color: str | None = Field(default=None, pattern=PATRON_COLOR)


class CategoryUpdateRequest(BaseModel):
    """Solo nombre y color.

    El tipo no se puede cambiar: pasar una categoría de gasto a ingreso
    convertiría sus movimientos históricos en lo contrario de lo que se
    registró, sin que el balance ni los reportes puedan notarlo.
    """

    model_config = _CONFIG_REQUEST

    name: str | None = Field(default=None, min_length=1, max_length=60)
    color: str | None = Field(default=None, pattern=PATRON_COLOR)

    @model_validator(mode="after")
    def _exigir_algun_cambio(self) -> Self:
        if self.name is None and self.color is None:
            raise ValueError("Indicá al menos un campo a modificar.")
        return self


class CategoryResponse(BaseModel):
    id: int
    name: str
    type: TransactionType
    color: str | None
    is_default: bool
