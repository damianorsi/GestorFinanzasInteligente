"""Schemas del asistente conversacional."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.application.dtos import ChatMessage
from app.domain.enums import ChatRole

LARGO_MAXIMO_MENSAJE = 1000


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        min_length=1,
        max_length=LARGO_MAXIMO_MENSAJE,
        description="Consulta en lenguaje natural.",
    )

    conversation_id: str | None = Field(
        default=None,
        max_length=36,
        description="Para continuar una conversación. Si se omite, se abre una nueva.",
    )

    @field_validator("message")
    @classmethod
    def _sin_espacios_al_borde(cls, valor: str) -> str:
        """Recorta y rechaza un mensaje en blanco.

        `min_length` solo no alcanza: un mensaje de puros espacios lo pasa, se
        persiste y se le paga una consulta al modelo por nada.
        """
        recortado = valor.strip()
        if not recortado:
            raise ValueError("El mensaje no puede estar vacío.")
        return recortado


class ChatResponse(BaseModel):
    conversation_id: str
    content: str
    # `degraded` distingue una respuesta de fallback de un "no sé" real del
    # asistente: sin esto, el frontend no puede ofrecer reintentar.
    degraded: bool


class ChatMessageResponse(BaseModel):
    role: ChatRole
    content: str
    created_at: datetime

    @classmethod
    def desde(cls, mensaje: ChatMessage) -> ChatMessageResponse:
        return cls(role=mensaje.role, content=mensaje.content, created_at=mensaje.created_at)
