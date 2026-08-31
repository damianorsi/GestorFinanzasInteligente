"""Todo lo que habla con el modelo: el agente del chat y el lector de tickets.

Comparten paquete porque comparten el cliente y el mismo criterio de errores:
ninguna excepción del SDK sale de acá sin traducirse a un error de dominio.
"""

from app.infrastructure.assistant.agent import LangChainAssistant
from app.infrastructure.assistant.receipt_reader import OpenAIReceiptReader
from app.infrastructure.assistant.tools import (
    DependenciasDelAsistente,
    construir_herramientas,
)

__all__ = [
    "DependenciasDelAsistente",
    "LangChainAssistant",
    "OpenAIReceiptReader",
    "construir_herramientas",
]
