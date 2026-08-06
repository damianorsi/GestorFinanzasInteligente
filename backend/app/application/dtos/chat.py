"""DTOs del asistente conversacional."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.enums import ChatRole


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: ChatRole
    content: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Consumo de una consulta al asistente.

    Se persiste desde la primera para poder recalibrar modelo y límites con
    datos reales en vez de con estimaciones (docs/PROMPT.md §11).
    """

    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tool_calls_count: int = 0


@dataclass(frozen=True, slots=True)
class AssistantAnswer:
    content: str
    usage: TokenUsage
    # `degraded` marca las respuestas de fallback: la persona recibió algo
    # legible, pero el agente no llegó a contestar. Sirve para no confundir un
    # "no sé" real con una caída de OpenAI al mirar el historial.
    degraded: bool = False


@dataclass(frozen=True, slots=True)
class TemporalContext:
    """Fechas ya resueltas que se le pasan al agente.

    El modelo no calcula fechas: recibe hoy y los rangos de los períodos
    habituales ya computados con el `Clock`, y elige entre ellos. Dejarle la
    aritmética de calendario al LLM es pedirle que adivine en qué zona horaria
    está parado.
    """

    today: str
    current_month: str
    current_month_from: str
    current_month_to: str
    previous_month: str
    previous_month_from: str
    previous_month_to: str
    extras: dict[str, str] = field(default_factory=dict)
