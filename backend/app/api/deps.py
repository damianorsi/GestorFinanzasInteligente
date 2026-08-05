"""Dependencias compartidas por los endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import session_scope


async def get_db() -> AsyncIterator[AsyncSession]:
    """Sesión de base de datos con alcance de request."""
    async with session_scope() as session:
        yield session
