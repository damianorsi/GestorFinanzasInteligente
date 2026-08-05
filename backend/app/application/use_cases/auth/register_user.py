"""Caso de uso: registro de una cuenta nueva."""

from __future__ import annotations

import logging

from app.application.exceptions import EmailAlreadyRegisteredError
from app.application.ports import CategoryRepository, PasswordHasher, UserRepository
from app.domain.default_categories import construir_categorias_por_defecto
from app.domain.entities import User

logger = logging.getLogger(__name__)


class RegisterUser:
    """Crea la cuenta y la deja usable desde el primer minuto.

    Sembrar las categorías por defecto es parte del registro y no un paso
    aparte: una cuenta sin categorías no puede registrar un solo movimiento.
    """

    def __init__(
        self,
        users: UserRepository,
        categories: CategoryRepository,
        hasher: PasswordHasher,
    ) -> None:
        self._users = users
        self._categories = categories
        self._hasher = hasher

    async def execute(self, email: str, password: str, full_name: str) -> User:
        # La entidad normaliza el email (recorta y pasa a minúsculas) antes de
        # que se consulte la unicidad, para que "A@B.com" y "a@b.com" no
        # terminen siendo dos cuentas distintas.
        usuario = User(email=email, full_name=full_name)

        if await self._users.exists_with_email(usuario.email):
            raise EmailAlreadyRegisteredError("Ya existe una cuenta con ese email.")

        creado = await self._users.create(usuario, self._hasher.hash(password))
        if creado.id is None:
            raise RuntimeError("El repositorio devolvió un usuario sin id asignado.")

        await self._categories.create_many(construir_categorias_por_defecto(creado.id))

        # Se loguea el id y nunca el email: es un dato personal.
        logger.info("Cuenta creada", extra={"user_id": creado.id})
        return creado
