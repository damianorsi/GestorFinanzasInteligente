"""Agente conversacional sobre LangChain."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import InputAgentState, ModelCallLimitMiddleware
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from app.application.dtos import (
    AssistantAnswer,
    ChatMessage,
    TemporalContext,
    TokenUsage,
)
from app.application.exceptions import AssistantUnavailableError
from app.domain.enums import ChatRole

from .prompt import construir_prompt_de_sistema
from .tools import DependenciasDelAsistente, construir_herramientas

logger = logging.getLogger(__name__)

# Margen sobre el timeout del cliente HTTP: si el corte propio saltara antes que
# el del SDK, nunca veríamos el error real de OpenAI y todo parecería un timeout
# nuestro.
MARGEN_DE_TIMEOUT_SEGUNDOS = 5

MENSAJE_SIN_CONVERGER = (
    "Tu consulta me llevó a dar muchas vueltas y preferí frenar antes de "
    "inventar algo. ¿Podés preguntarme algo más puntual? Por ejemplo, "
    "«¿cuánto gasté este mes?» o «¿cómo voy con el presupuesto de agosto?»."
)


class ContadorDeUso(BaseCallbackHandler):
    """Acumula tokens y llamadas a herramientas de toda la corrida.

    Se implementa a mano en vez de usar `get_openai_callback` para no depender
    de `langchain-community`, que traería medio ecosistema por un contador.

    Va por callbacks y no leyendo los mensajes de la respuesta porque cuando el
    agente corta por tope de llamadas no hay respuesta que leer, y ese consumo
    igual se facturó.
    """

    def __init__(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.tool_calls = 0

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        uso = (getattr(response, "llm_output", None) or {}).get("token_usage") or {}

        if not uso:
            # Algunas versiones devuelven el consumo en el mensaje y no en
            # `llm_output`; se buscan los dos para no perder la telemetría al
            # actualizar la librería.
            for generacion in getattr(response, "generations", []) or []:
                for item in generacion:
                    mensaje = getattr(item, "message", None)
                    metadatos = getattr(mensaje, "usage_metadata", None) or {}
                    if metadatos:
                        uso = {
                            "prompt_tokens": metadatos.get("input_tokens", 0),
                            "completion_tokens": metadatos.get("output_tokens", 0),
                            "total_tokens": metadatos.get("total_tokens", 0),
                        }
                        break

        self.prompt_tokens += int(uso.get("prompt_tokens", 0) or 0)
        self.completion_tokens += int(uso.get("completion_tokens", 0) or 0)
        self.total_tokens += int(uso.get("total_tokens", 0) or 0)

    def on_tool_start(self, serialized: Any, input_str: str, **kwargs: Any) -> None:
        self.tool_calls += 1


def _a_mensajes(history: Sequence[ChatMessage]) -> list[AIMessage | HumanMessage]:
    return [
        HumanMessage(content=mensaje.content)
        if mensaje.role is ChatRole.USER
        else AIMessage(content=mensaje.content)
        for mensaje in history
    ]


class LangChainAssistant:
    """Implementación del puerto `ChatAgent`."""

    def __init__(
        self,
        deps: DependenciasDelAsistente,
        api_key: str,
        model: str,
        max_tokens: int,
        max_iterations: int,
        timeout_seconds: int,
    ) -> None:
        self._deps = deps
        self._model_name = model
        self._max_iterations = max_iterations
        self._timeout_seconds = timeout_seconds
        self._llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            max_completion_tokens=max_tokens,
            timeout=timeout_seconds,
            max_retries=1,
        )

    async def answer(
        self,
        user_id: int,
        message: str,
        history: Sequence[ChatMessage],
        temporal: TemporalContext,
    ) -> AssistantAnswer:
        # Las herramientas se construyen por consulta porque llevan el user_id
        # cerrado adentro. Reutilizar un agente entre usuarios sería
        # exactamente el bug que este diseño evita.
        herramientas = construir_herramientas(user_id, self._deps)

        agente = create_agent(
            self._llm,
            tools=herramientas,
            system_prompt=construir_prompt_de_sistema(temporal),
            # Sin tope, el agente puede entrar en loop herramienta -> modelo ->
            # herramienta y hacer decenas de llamadas en una sola consulta.
            # `error` en vez de `end` para distinguir el corte de una respuesta
            # legítima sin tener que adivinar por el texto.
            middleware=[
                ModelCallLimitMiddleware(run_limit=self._max_iterations, exit_behavior="error")
            ],
        )

        contador = ContadorDeUso()
        entrada: InputAgentState = {
            "messages": [*_a_mensajes(history), HumanMessage(content=message)]
        }
        configuracion: RunnableConfig = {"callbacks": [contador]}

        try:
            resultado: dict[str, Any] = await asyncio.wait_for(
                agente.ainvoke(entrada, configuracion),
                timeout=self._timeout_seconds + MARGEN_DE_TIMEOUT_SEGUNDOS,
            )
        except ModelCallLimitExceededError:
            logger.info(
                "El agente no convergió dentro del tope de llamadas",
                extra={"user_id": user_id, "max_iterations": self._max_iterations},
            )
            return AssistantAnswer(
                content=MENSAJE_SIN_CONVERGER, usage=self._uso(contador), degraded=True
            )
        except TimeoutError as exc:
            raise AssistantUnavailableError("El asistente tardó demasiado.") from exc
        except Exception as exc:
            # Cualquier fallo del SDK o de la red se traduce a un error de
            # dominio: arriba no tiene por qué conocer las excepciones de OpenAI.
            logger.warning("Falló la consulta al modelo", extra={"error_type": type(exc).__name__})
            raise AssistantUnavailableError("El asistente no está disponible.") from exc

        mensajes: list[BaseMessage] = resultado.get("messages") or []
        salida = str(mensajes[-1].text).strip() if mensajes else ""
        uso = self._uso(contador)

        if not salida:
            return AssistantAnswer(content=MENSAJE_SIN_CONVERGER, usage=uso, degraded=True)

        return AssistantAnswer(content=salida, usage=uso)

    def _uso(self, contador: ContadorDeUso) -> TokenUsage:
        return TokenUsage(
            model=self._model_name,
            prompt_tokens=contador.prompt_tokens,
            completion_tokens=contador.completion_tokens,
            total_tokens=contador.total_tokens,
            tool_calls_count=contador.tool_calls,
        )
