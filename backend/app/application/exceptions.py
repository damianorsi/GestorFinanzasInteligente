"""Errores de los casos de uso.

No conocen HTTP: son la capa de aplicación. El mapeo a códigos y estados vive
en `app/core/errors.py`, del lado de la presentación.
"""

from __future__ import annotations


class ApplicationError(Exception):
    """Raíz de los errores de casos de uso."""


class EmailAlreadyRegisteredError(ApplicationError):
    """Ya existe una cuenta con ese email."""


class InvalidCredentialsError(ApplicationError):
    """Email o contraseña incorrectos.

    Es deliberadamente un único error para los dos casos: distinguir "el email
    no existe" de "la contraseña no coincide" convierte al login en un oráculo
    para enumerar cuentas registradas.
    """


class InvalidTokenError(ApplicationError):
    """El token es inválido, expiró o fue revocado."""


class InactiveUserError(ApplicationError):
    """La cuenta existe pero está deshabilitada."""


class ResourceNotFoundError(ApplicationError):
    """El recurso no existe, o es de otro usuario.

    Los dos casos son el mismo error a propósito: responder 403 en vez de 404
    para un recurso ajeno confirma que ese identificador existe.
    """


class DuplicateResourceError(ApplicationError):
    """Ya existe otro recurso con los mismos datos identificatorios."""


class UnsupportedCurrencyError(ApplicationError):
    """La moneda pedida no está habilitada.

    En v1 solo ARS. El esquema y el dominio ya soportan más, pero habilitarlas
    exige antes decidir la política de tipo de cambio.
    """


class InvalidReferenceError(ApplicationError):
    """Un identificador del payload no apunta a un recurso propio y usable.

    Es 422 y no 404 a propósito: el recurso pedido —el movimiento— no es el que
    falta; lo que está mal es un dato del cuerpo del request.
    """


class RateLimitExceededError(ApplicationError):
    """Se superó el cupo de consultas al asistente."""


class AssistantUnavailableError(ApplicationError):
    """El proveedor del modelo falló o no respondió a tiempo.

    Se distingue de un error interno porque no es un bug: es una dependencia
    externa caída, y la respuesta correcta es un mensaje claro y no un 500.
    """


class ReceiptUnreadableError(ApplicationError):
    """El archivo no es un ticket que se pueda leer.

    Se distingue de `AssistantUnavailableError` a propósito: acá el proveedor
    contestó bien y el problema es la imagen. Uno se reintenta, el otro se
    resuelve sacando mejor la foto o cargando el gasto a mano.
    """


class UnsupportedFileTypeError(ApplicationError):
    """El archivo no tiene un formato aceptado, o pesa de más."""


class ExportTooLargeError(ApplicationError):
    """La exportación pedida no entra en una sola respuesta.

    Se avisa en vez de truncar: un CSV recortado en silencio es peor que un
    error, porque parece completo.
    """


class ResourceInUseError(ApplicationError):
    """El recurso no se puede borrar porque otros dependen de él.

    El mensaje enumera qué lo está bloqueando: un 409 que solo dice "está en
    uso" obliga a la persona usuaria a adivinar qué tiene que borrar antes.
    """


__all__ = [
    "ApplicationError",
    "AssistantUnavailableError",
    "DuplicateResourceError",
    "EmailAlreadyRegisteredError",
    "ExportTooLargeError",
    "InactiveUserError",
    "InvalidCredentialsError",
    "InvalidReferenceError",
    "InvalidTokenError",
    "RateLimitExceededError",
    "ReceiptUnreadableError",
    "ResourceInUseError",
    "ResourceNotFoundError",
    "UnsupportedCurrencyError",
    "UnsupportedFileTypeError",
]
