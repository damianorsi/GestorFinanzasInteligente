"""Dobles de prueba en memoria para los casos de uso.

Son *fakes* y no mocks: tienen una implementación real, simple y sin I/O. Eso
permite testear el comportamiento del caso de uso en vez de verificar qué
métodos llamó, que es lo que termina rompiéndose en cada refactor.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

from app.application.dtos import StoredRefreshToken, UserCredentials
from app.domain.entities import Category, User


class FixedClock:
    """Reloj detenido, que se puede adelantar a mano."""

    def __init__(self, momento: datetime) -> None:
        self._momento = momento

    def now(self) -> datetime:
        return self._momento

    def today(self) -> date:
        return self._momento.date()

    def avanzar(self, delta: timedelta) -> None:
        self._momento += delta


class FakePasswordHasher:
    """Hasher trivial y reversible.

    Argon2 real tarda decenas de milisegundos por hash a propósito; usarlo en
    los tests de casos de uso los volvería lentos sin agregar información. El
    algoritmo real se testea aparte, en test_password_hasher.py.
    """

    PREFIJO = "hash:"

    def __init__(self) -> None:
        self.veces_que_verifico_descartable = 0

    def hash(self, plain: str) -> str:
        return f"{self.PREFIJO}{plain}"

    def verify(self, plain: str, hashed: str) -> bool:
        return hashed == self.hash(plain)

    def verify_dummy(self, plain: str) -> None:
        self.veces_que_verifico_descartable += 1


class FakeUserRepository:
    def __init__(self) -> None:
        self._por_id: dict[int, UserCredentials] = {}
        self._siguiente_id = 1

    async def exists_with_email(self, email: str) -> bool:
        return any(c.user.email == email for c in self._por_id.values())

    async def get_by_id(self, user_id: int) -> User | None:
        credenciales = self._por_id.get(user_id)
        return credenciales.user if credenciales is not None else None

    async def get_credentials_by_email(self, email: str) -> UserCredentials | None:
        for credenciales in self._por_id.values():
            if credenciales.user.email == email:
                return credenciales
        return None

    async def create(self, user: User, password_hash: str) -> User:
        user.id = self._siguiente_id
        self._siguiente_id += 1
        self._por_id[user.id] = UserCredentials(user=user, password_hash=password_hash)
        return user

    # --- Ayudas para los tests ---------------------------------------------
    def agregar(self, user: User, password_hash: str) -> User:
        if user.id is None:
            user.id = self._siguiente_id
            self._siguiente_id += 1
        self._por_id[user.id] = UserCredentials(user=user, password_hash=password_hash)
        return user


class FakeCategoryRepository:
    def __init__(self) -> None:
        self.categorias: list[Category] = []

    async def create_many(self, categories: Sequence[Category]) -> None:
        self.categorias.extend(categories)

    async def count_for_user(self, user_id: int) -> int:
        return sum(1 for c in self.categorias if c.user_id == user_id)


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self._tokens: dict[str, tuple[int, datetime, datetime | None]] = {}

    async def store(self, user_id: int, token_hash: str, expires_at: datetime) -> None:
        self._tokens[token_hash] = (user_id, expires_at, None)

    async def find_active(self, token_hash: str, now: datetime) -> StoredRefreshToken | None:
        registro = self._tokens.get(token_hash)
        if registro is None:
            return None
        user_id, expira, revocado = registro
        if revocado is not None or expira <= now:
            return None
        return StoredRefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expira)

    async def revoke(self, token_hash: str, now: datetime) -> None:
        registro = self._tokens.get(token_hash)
        if registro is not None and registro[2] is None:
            self._tokens[token_hash] = (registro[0], registro[1], now)

    async def revoke_all_for_user(self, user_id: int, now: datetime) -> None:
        for huella, (uid, expira, revocado) in list(self._tokens.items()):
            if uid == user_id and revocado is None:
                self._tokens[huella] = (uid, expira, now)
