"""Lector de tickets sobre un modelo con visión."""

from __future__ import annotations

import base64
import logging
from collections.abc import Sequence
from datetime import date
from decimal import Decimal, InvalidOperation

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.application.dtos import ExtractedReceipt
from app.application.exceptions import AssistantUnavailableError, ReceiptUnreadableError
from app.domain.entities import Category

logger = logging.getLogger(__name__)

CONFIANZA_MINIMA = 0.0
CONFIANZA_MAXIMA = 1.0

PROMPT = """\
Sos un lector de tickets de compra. Extraés datos de la foto y nada más.

REGLAS:

1. Devolvé SOLO lo que efectivamente leés en la imagen. Si un dato no está o no
   se entiende, dejalo en null. **Nunca inventes un valor ni lo estimes.** Un
   monto inventado se convierte en un gasto falso en las finanzas de alguien.
2. `amount` es el TOTAL pagado, no un subtotal ni el importe de un renglón.
   Sin símbolo de moneda ni separadores de miles: 12345.67
3. `occurred_on` es la fecha del ticket en formato AAAA-MM-DD. Si el ticket
   muestra la fecha en formato día/mes/año, convertila. Si no hay fecha, null.
4. `merchant` es el nombre del comercio, corto.
5. `category_name` tiene que ser **exactamente uno** de los nombres de esta
   lista, o null si ninguno corresponde. No inventes categorías nuevas:

{categorias}

6. `confidence` lleva un número de 0 a 1 por cada campo que hayas completado,
   con lo seguro que estás de esa lectura. Sé honesto: si el papel está
   arrugado y el total podría ser 1230 o 7230, poné una confianza baja. Es
   preferible una duda declarada que un dato firme y equivocado.

Si la imagen no es un ticket de compra —una foto de otra cosa, un texto
ilegible—, devolvé `legible` en false.\
"""


class _Lectura(BaseModel):
    """Esquema que se le exige al modelo. Todo opcional menos `legible`."""

    legible: bool = Field(description="False si la imagen no es un ticket legible.")
    amount: str | None = Field(default=None, description="Total pagado, sin símbolos.")
    occurred_on: str | None = Field(default=None, description="Fecha del ticket, AAAA-MM-DD.")
    merchant: str | None = Field(default=None, description="Nombre del comercio.")
    category_name: str | None = Field(default=None, description="Una de las categorías dadas.")
    confidence: dict[str, float] = Field(
        default_factory=dict, description="Confianza de 0 a 1 por campo completado."
    )


def _a_decimal(crudo: str | None) -> Decimal | None:
    if not crudo:
        return None
    try:
        valor = Decimal(crudo.replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None
    # Un total negativo o cero no es un ticket de compra. Se descarta en vez de
    # proponerlo: el formulario lo rechazaría igual, con un error más confuso.
    if valor <= 0:
        return None
    return valor.quantize(Decimal("0.01"))


def _a_fecha(crudo: str | None) -> date | None:
    if not crudo:
        return None
    try:
        return date.fromisoformat(crudo.strip()[:10])
    except ValueError:
        return None


def _acotar(confianza: dict[str, float]) -> dict[str, float]:
    """Deja la confianza dentro de 0 y 1.

    El modelo a veces devuelve porcentajes (85) en vez de proporciones (0.85);
    sin acotar, la interfaz mostraría un campo dudoso como si fuera certero.
    """
    acotada: dict[str, float] = {}
    for campo, valor in confianza.items():
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            continue
        if numero > CONFIANZA_MAXIMA:
            numero = numero / 100
        acotada[campo] = min(max(numero, CONFIANZA_MINIMA), CONFIANZA_MAXIMA)
    return acotada


class OpenAIReceiptReader:
    """Implementación del puerto `ReceiptReader`."""

    def __init__(self, api_key: str, model: str, timeout_seconds: int) -> None:
        self._llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            timeout=timeout_seconds,
            max_retries=1,
        ).with_structured_output(_Lectura)

    async def read(
        self, image: bytes, mime_type: str, categories: Sequence[Category]
    ) -> ExtractedReceipt:
        nombres = "\n".join(f"- {categoria.name}" for categoria in categories) or "- (ninguna)"
        # La imagen viaja como data URL en el mismo mensaje. No se escribe a
        # disco en ningún momento: se procesa en memoria y se descarta.
        codificada = base64.b64encode(image).decode("ascii")

        mensaje = HumanMessage(
            content=[
                {"type": "text", "text": PROMPT.format(categorias=nombres)},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{codificada}"},
                },
            ]
        )

        try:
            lectura = await self._llm.ainvoke([mensaje])
        except Exception as exc:
            # Igual que el chat: las excepciones del SDK no salen de acá.
            logger.warning("Falló la lectura del ticket", extra={"error_type": type(exc).__name__})
            raise AssistantUnavailableError("No se pudo leer el ticket en este momento.") from exc

        if not isinstance(lectura, _Lectura) or not lectura.legible:
            raise ReceiptUnreadableError(
                "No pude leer el ticket. Probá con una foto más nítida, o cargá el gasto a mano."
            )

        monto = _a_decimal(lectura.amount)
        if monto is None:
            # Sin total no hay borrador que valga: el resto de los campos no
            # alcanzan para proponer un movimiento.
            raise ReceiptUnreadableError(
                "Leí el ticket pero no encontré el total. Probá con una foto "
                "donde se vea el importe final."
            )

        return ExtractedReceipt(
            amount=monto,
            occurred_on=_a_fecha(lectura.occurred_on),
            merchant=(lectura.merchant or "").strip()[:120] or None,
            category_name=lectura.category_name,
            confidence=_acotar(lectura.confidence),
        )
