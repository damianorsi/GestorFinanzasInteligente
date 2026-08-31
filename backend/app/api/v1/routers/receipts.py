"""Endpoints de lectura de tickets."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import CurrentUser, get_scan_receipt
from app.api.v1.schemas.receipts import ReceiptDraftResponse
from app.application.use_cases.receipts import ScanReceipt

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post(
    "/scan",
    response_model=ReceiptDraftResponse,
    summary="Leer un ticket y proponer el movimiento",
    description=(
        "Recibe la foto de un ticket y devuelve un **borrador** con monto, fecha, "
        "comercio y categoría sugerida entre las del usuario, con la confianza de cada "
        "campo.\n\n"
        "**No crea ningún movimiento**: la confirmación pasa por `POST /transactions`, "
        "con las mismas validaciones de siempre. Un lector que escribe montos mal leídos "
        "en silencio deja el error en el historial y contamina reportes y presupuestos.\n\n"
        "**La imagen no se persiste**: se procesa en memoria y se descarta.\n\n"
        "Devuelve 422 si el archivo no es una imagen aceptada, si pesa de más o si el "
        "ticket es ilegible; 429 al superar el cupo por hora; y 503 si el proveedor del "
        "modelo falla."
    ),
)
async def escanear(
    usuario: CurrentUser,
    caso: Annotated[ScanReceipt, Depends(get_scan_receipt)],
    file: Annotated[UploadFile, File(description="Foto del ticket: JPEG, PNG o WebP.")],
) -> ReceiptDraftResponse:
    contenido = await file.read()
    borrador = await caso.execute(
        user_id=usuario.id or 0,
        image=contenido,
        mime_type=file.content_type or "",
    )
    return ReceiptDraftResponse.desde(borrador)
