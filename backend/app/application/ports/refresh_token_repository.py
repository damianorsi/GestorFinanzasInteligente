"""Puerto de persistencia de refresh tokens.

Se guardan para poder revocarlos: un JWT por sí solo es válido hasta que
expira, así que sin este registro un logout no podría invalidar nada.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.application.dtos import StoredRefreshToken


class RefreshTokenRepository(Protocol):
    async def store(self, user_id: int, token_hash: str, expires_at: datetime) -> None: ...

    async def find_active(self, token_hash: str, now: datetime) -> StoredRefreshToken | None:
        """Busca un token no revocado y no vencido."""
        ...

    async def revoke(self, token_hash: str, now: datetime) -> None:
        """Marca el token como revocado. Idempotente."""
        ...

    async def revoke_all_for_user(self, user_id: int, now: datetime) -> None:
        """Revoca todos los tokens vigentes de un usuario."""
        ...
