"""Errores de aplicación y sus handlers HTTP.

Contrato de error (docs/PROMPT.md §7):

    { "code": "snake_case_en_ingles", "message": "texto en español", "details": [...] }

`code` es estable y en inglés — el frontend mapea por `code`, nunca por el
texto de `message`. `message` va en español porque lo lee la persona usuaria.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.application.exceptions import (
    ApplicationError,
    DuplicateResourceError,
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidReferenceError,
    InvalidTokenError,
    ResourceInUseError,
    ResourceNotFoundError,
    UnsupportedCurrencyError,
)
from app.domain.exceptions import DomainError

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Error de negocio con código estable y estado HTTP asociado."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "Ocurrió un error inesperado."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or []
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "El recurso solicitado no existe."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "El recurso ya existe o está en uso."


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"
    message = "Los datos enviados no son válidos."


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "Credenciales inválidas o sesión expirada."


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    respuesta = JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "details": details or []},
    )
    if status_code == status.HTTP_401_UNAUTHORIZED:
        respuesta.headers["WWW-Authenticate"] = "Bearer"
    return respuesta


# Traducción de los errores de la capa de aplicación a la respuesta HTTP.
# El mapeo vive acá y no en `application/` para que los casos de uso no tengan
# que conocer códigos de estado.
# Respuestas de los errores que levanta el propio framework (body ilegible,
# ruta inexistente, método no permitido). Traen el texto en inglés, así que se
# reemplaza por el propio para no romper el contrato.
_MENSAJES_HTTP: dict[int, tuple[str, str]] = {
    status.HTTP_400_BAD_REQUEST: ("bad_request", "No se pudo interpretar la solicitud."),
    status.HTTP_401_UNAUTHORIZED: ("unauthorized", "Credenciales inválidas o sesión expirada."),
    status.HTTP_403_FORBIDDEN: ("forbidden", "No tenés permiso para acceder a este recurso."),
    status.HTTP_404_NOT_FOUND: ("not_found", "El recurso solicitado no existe."),
    status.HTTP_405_METHOD_NOT_ALLOWED: (
        "method_not_allowed",
        "El método HTTP no está permitido para este recurso.",
    ),
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: (
        "unsupported_media_type",
        "El tipo de contenido no está soportado.",
    ),
    status.HTTP_429_TOO_MANY_REQUESTS: (
        "rate_limit_exceeded",
        "Demasiadas solicitudes. Probá de nuevo en unos minutos.",
    ),
}

_MAPEO_APLICACION: dict[type[ApplicationError], tuple[int, str]] = {
    EmailAlreadyRegisteredError: (status.HTTP_409_CONFLICT, "email_already_registered"),
    InvalidCredentialsError: (status.HTTP_401_UNAUTHORIZED, "invalid_credentials"),
    InvalidTokenError: (status.HTTP_401_UNAUTHORIZED, "invalid_token"),
    InactiveUserError: (status.HTTP_403_FORBIDDEN, "inactive_user"),
    ResourceNotFoundError: (status.HTTP_404_NOT_FOUND, "not_found"),
    DuplicateResourceError: (status.HTTP_409_CONFLICT, "duplicate_resource"),
    ResourceInUseError: (status.HTTP_409_CONFLICT, "resource_in_use"),
    UnsupportedCurrencyError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "unsupported_currency",
    ),
    InvalidReferenceError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_reference"),
}


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los handlers globales. Nunca se devuelve un stacktrace."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(ApplicationError)
    async def _handle_application_error(_: Request, exc: ApplicationError) -> JSONResponse:
        # Se recorre el MRO para que una subclase futura herede el mapeo de su
        # padre en vez de caer al 400 genérico sin que nadie lo note.
        for clase in type(exc).__mro__:
            if clase in _MAPEO_APLICACION:
                status_code, code = _MAPEO_APLICACION[clase]
                return _error_response(status_code, code, str(exc))
        logger.warning(
            "Error de aplicación sin mapeo HTTP",
            extra={"error_type": type(exc).__name__},
        )
        return _error_response(status.HTTP_400_BAD_REQUEST, "application_error", str(exc))

    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        # Una invariante de dominio violada es, desde afuera, un dato inválido.
        return _error_response(status.HTTP_422_UNPROCESSABLE_CONTENT, "validation_error", str(exc))

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in err.get("loc", []) if part != "body"),
                "reason": err.get("msg", ""),
            }
            for err in exc.errors()
        ]
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_error",
            "Los datos enviados no son válidos.",
            details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # No se reenvía `exc.detail`: los errores que levanta el framework
        # traen el texto en inglés ("There was an error parsing the body") y el
        # contrato dice que `message` va en español. El código de la aplicación
        # nunca lanza StarletteHTTPException, así que no se pierde nada propio.
        code, mensaje = _MENSAJES_HTTP.get(
            exc.status_code, ("http_error", "No se pudo procesar la solicitud.")
        )
        return _error_response(exc.status_code, code, mensaje)

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Excepción no controlada", extra={"error_type": type(exc).__name__})
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "Ocurrió un error inesperado.",
        )
