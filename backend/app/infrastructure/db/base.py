"""Base declarativa de SQLAlchemy.

Los modelos concretos llegan en la fase 2. Alembic importa `Base.metadata`
desde acá para autogenerar migraciones.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base común de todos los modelos ORM."""
