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


__all__ = [
    "ApplicationError",
    "EmailAlreadyRegisteredError",
    "InactiveUserError",
    "InvalidCredentialsError",
    "InvalidTokenError",
    "ResourceNotFoundError",
]
