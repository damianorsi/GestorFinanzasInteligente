"""Puerto de hashing de contraseñas."""

from __future__ import annotations

from typing import Protocol


class PasswordHasher(Protocol):
    """Algoritmo de hashing. La implementación concreta vive en infrastructure."""

    def hash(self, plain: str) -> str:
        """Devuelve el hash de una contraseña en claro."""
        ...

    def verify(self, plain: str, hashed: str) -> bool:
        """Verifica una contraseña contra su hash."""
        ...

    def verify_dummy(self, plain: str) -> None:
        """Hace el mismo trabajo que `verify` pero contra un hash descartable.

        Se usa en el login cuando el email no existe. Sin esto, la respuesta
        para un email inexistente vuelve mucho más rápido que para uno real
        —porque se saltea el hashing, que es caro a propósito— y esa diferencia
        de tiempo alcanza para enumerar qué cuentas están registradas.
        """
        ...
