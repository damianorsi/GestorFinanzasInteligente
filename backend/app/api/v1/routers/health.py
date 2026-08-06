"""Health check de la aplicación.

Lo consume el `healthcheck` del contenedor y, más adelante, el monitoreo.
No va bajo `/api/v1`: es un endpoint de infraestructura, no de negocio.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.infrastructure.db.session import get_engine
from app.infrastructure.scheduler import estado as estado_del_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(tags=["infra"])


class HealthResponse(BaseModel):
    status: str
    environment: str
    timezone: str
    default_currency: str
    database: str
    # `disabled` (no arrancó), `pending` (arrancó y todavía no corrió), `ok` o
    # `error`. Se informa el estado de **este** proceso: con varias réplicas,
    # cada una tiene su propio scheduler.
    scheduler: str
    scheduler_last_run: datetime | None = None


async def _check_database() -> bool:
    """Verifica conectividad real contra MySQL con un SELECT 1."""
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        # El health check nunca debe propagar: informa el estado, no falla.
        logger.warning(
            "Health check de base de datos falló",
            extra={"error_type": type(exc).__name__},
        )
        return False
    return True


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Estado de la aplicación",
    description=(
        "Devuelve 200 si la aplicación y la base de datos responden, 503 en caso contrario."
    ),
)
async def health(response: Response) -> HealthResponse:
    settings = get_settings()
    db_ok = await _check_database()

    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        environment=settings.app_env,
        timezone=settings.app_timezone,
        default_currency=settings.default_currency,
        database="ok" if db_ok else "error",
        scheduler=estado_del_scheduler.estado,
        scheduler_last_run=estado_del_scheduler.ultima_corrida,
    )
