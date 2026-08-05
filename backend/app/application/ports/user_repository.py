"""Puerto de persistencia de usuarios."""

from __future__ import annotations

from typing import Protocol

from app.application.dtos import UserCredentials
from app.domain.entities import User


class UserRepository(Protocol):
    async def exists_with_email(self, email: str) -> bool:
        """Si ya hay una cuenta con ese email."""
        ...

    async def get_by_id(self, user_id: int) -> User | None: ...

    async def get_credentials_by_email(self, email: str) -> UserCredentials | None:
        """Devuelve el usuario junto a su hash de contraseña, o None.

        Es el único método que expone el hash, y existe solo para el login.
        """
        ...

    async def create(self, user: User, password_hash: str) -> User:
        """Persiste el usuario y lo devuelve con su `id` asignado."""
        ...
