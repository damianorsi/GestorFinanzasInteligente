"""Hashing de contraseñas con Argon2id."""

from __future__ import annotations

from contextlib import suppress

from argon2 import PasswordHasher as Argon2
from argon2.exceptions import InvalidHashError, VerificationError

# Contraseña arbitraria usada solo para generar el hash contra el que se
# compara cuando el email no existe. No autentica a nadie.
_TEXTO_DESCARTABLE = "contrasena-descartable-para-igualar-tiempos"


class Argon2Hasher:
    """Implementación del puerto `PasswordHasher`.

    Argon2id con los parámetros por defecto de argon2-cffi, que siguen la
    recomendación de OWASP. Se eligió sobre bcrypt porque bcrypt trunca en
    silencio a 72 bytes: una contraseña larga quedaría parcialmente ignorada.
    """

    def __init__(self) -> None:
        self._argon2 = Argon2()
        # Se calcula una vez al arrancar: es caro a propósito, y hacerlo en
        # cada login fallido duplicaría el trabajo sin ganar nada.
        self._hash_descartable = self._argon2.hash(_TEXTO_DESCARTABLE)

    def hash(self, plain: str) -> str:
        return self._argon2.hash(plain)

    def verify(self, plain: str, hashed: str) -> bool:
        try:
            self._argon2.verify(hashed, plain)
        except (VerificationError, InvalidHashError):
            return False
        return True

    def verify_dummy(self, plain: str) -> None:
        """Gasta el mismo tiempo que un `verify` real y descarta el resultado."""
        with suppress(VerificationError, InvalidHashError):
            self._argon2.verify(self._hash_descartable, plain)
