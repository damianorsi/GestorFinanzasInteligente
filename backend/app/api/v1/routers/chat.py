"""Endpoints del asistente conversacional."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, get_ask_assistant, get_chat_history
from app.api.v1.schemas.chat import ChatMessageResponse, ChatRequest, ChatResponse
from app.application.use_cases.chat import AskAssistant, GetChatHistory

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Consultar al asistente",
    description=(
        "Responde en lenguaje natural sobre los movimientos del usuario autenticado. "
        "El asistente solo accede a los datos de quien pregunta: el identificador no es "
        "un parámetro que el modelo pueda elegir. Devuelve 429 al superar el cupo por "
        "hora, y una respuesta degradada —nunca un 500— si el proveedor del modelo falla."
    ),
)
async def preguntar(
    payload: ChatRequest,
    usuario: CurrentUser,
    caso: Annotated[AskAssistant, Depends(get_ask_assistant)],
) -> ChatResponse:
    conversacion, respuesta = await caso.execute(
        user_id=usuario.id or 0,
        message=payload.message,
        conversation_id=payload.conversation_id,
    )
    return ChatResponse(
        conversation_id=conversacion,
        content=respuesta.content,
        degraded=respuesta.degraded,
    )


@router.get(
    "/history",
    response_model=list[ChatMessageResponse],
    summary="Historial de una conversación",
    description="Devuelve los últimos mensajes, en orden cronológico.",
)
async def historial(
    usuario: CurrentUser,
    caso: Annotated[GetChatHistory, Depends(get_chat_history)],
    conversation_id: Annotated[str, Query(max_length=36)],
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> list[ChatMessageResponse]:
    mensajes = await caso.execute(usuario.id or 0, conversation_id, limit)
    return [ChatMessageResponse.desde(mensaje) for mensaje in mensajes]
