"""Punto de entrada de la aplicación FastAPI."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.v1.routers import health
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, request_id_var
from app.infrastructure.db.session import dispose_engine
from app.infrastructure.scheduler import iniciar_scheduler

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "Aplicación iniciada",
        extra={
            "environment": settings.app_env,
            "timezone": settings.app_timezone,
            "default_currency": settings.default_currency,
        },
    )
    scheduler = iniciar_scheduler(settings)
    yield
    if scheduler is not None:
        # `wait=False` para no bloquear el apagado si el job está corriendo: la
        # idempotencia del caso de uso hace que retomarlo mañana sea seguro.
        scheduler.shutdown(wait=False)
    await dispose_engine()
    logger.info("Aplicación detenida")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Gestor Inteligente de Finanzas Personales",
        description=(
            "API de gestión de finanzas personales con asistente conversacional. "
            "Montos en formato string con punto decimal; fechas en ISO 8601."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _correlacionar_request(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Asigna un `request_id` para correlacionar todos los logs del request."""
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(api_router)

    return app


app = create_app()
