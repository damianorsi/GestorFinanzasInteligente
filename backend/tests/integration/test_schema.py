"""Tests del esquema contra MySQL real.

Verifican las garantías que la base tiene que dar por sí sola, sin depender de
que el código las respete: constraints de unicidad, comportamiento de borrado
en cascada y precisión decimal de los montos.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OccurrenceStatus, RecurrenceFrequency, TransactionType
from app.infrastructure.db.models import (
    BudgetModel,
    CategoryModel,
    RecurringOccurrenceModel,
    RecurringRuleModel,
    TransactionModel,
    UserModel,
)

pytestmark = pytest.mark.integration


async def _crear_usuario(session: AsyncSession, email: str = "test@ejemplo.com") -> UserModel:
    usuario = UserModel(email=email, password_hash="hash-falso", full_name="Test")
    session.add(usuario)
    await session.flush()
    return usuario


async def _crear_categoria(
    session: AsyncSession,
    user_id: int,
    nombre: str = "Alimentación",
    tipo: TransactionType = TransactionType.EXPENSE,
) -> CategoryModel:
    categoria = CategoryModel(user_id=user_id, name=nombre, type=tipo)
    session.add(categoria)
    await session.flush()
    return categoria


async def _crear_movimiento(
    session: AsyncSession,
    user_id: int,
    category_id: int,
    monto: str = "100.00",
    **extra: object,
) -> TransactionModel:
    movimiento = TransactionModel(
        user_id=user_id,
        category_id=category_id,
        type=TransactionType.EXPENSE,
        amount=Decimal(monto),
        occurred_on=date(2026, 8, 4),
        **extra,
    )
    session.add(movimiento)
    await session.flush()
    return movimiento


async def _crear_regla(session: AsyncSession, user_id: int, category_id: int) -> RecurringRuleModel:
    regla = RecurringRuleModel(
        user_id=user_id,
        category_id=category_id,
        type=TransactionType.EXPENSE,
        amount=Decimal("850000.00"),
        frequency=RecurrenceFrequency.MONTHLY,
        day_of_month=5,
        starts_on=date(2026, 1, 1),
    )
    session.add(regla)
    await session.flush()
    return regla


# --- Migración -------------------------------------------------------------
async def test_la_migracion_quedo_aplicada(db_session: AsyncSession) -> None:
    # Arrange / Act
    resultado = await db_session.execute(text("SELECT version_num FROM alembic_version"))

    # Assert
    assert resultado.scalar_one()


# --- Moneda ----------------------------------------------------------------
async def test_la_moneda_por_defecto_es_ars(db_session: AsyncSession) -> None:
    """Insertar sin moneda tiene que dar ARS, no NULL ni cadena vacía."""
    # Arrange
    usuario = await _crear_usuario(db_session)
    categoria = await _crear_categoria(db_session, usuario.id)

    # Act
    movimiento = await _crear_movimiento(db_session, usuario.id, categoria.id)
    await db_session.refresh(movimiento)

    # Assert
    assert movimiento.currency == "ARS"


# --- Precisión decimal -----------------------------------------------------
@pytest.mark.parametrize("monto", ["0.01", "1234.56", "99999999999.99"])
async def test_los_montos_conservan_los_decimales_exactos(
    db_session: AsyncSession, monto: str
) -> None:
    """DECIMAL(14,2) y no FLOAT: los centavos tienen que volver intactos."""
    # Arrange
    usuario = await _crear_usuario(db_session)
    categoria = await _crear_categoria(db_session, usuario.id)

    # Act
    movimiento = await _crear_movimiento(db_session, usuario.id, categoria.id, monto=monto)
    db_session.expunge(movimiento)
    recuperado = await db_session.get(TransactionModel, movimiento.id)

    # Assert
    assert recuperado is not None
    assert recuperado.amount == Decimal(monto)


# --- Unicidad --------------------------------------------------------------
async def test_no_permite_categorias_duplicadas_por_usuario_nombre_y_tipo(
    db_session: AsyncSession,
) -> None:
    # Arrange
    usuario = await _crear_usuario(db_session)
    await _crear_categoria(db_session, usuario.id, "Ocio")

    # Act
    db_session.add(CategoryModel(user_id=usuario.id, name="Ocio", type=TransactionType.EXPENSE))

    # Assert
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_permite_el_mismo_nombre_en_tipos_distintos(db_session: AsyncSession) -> None:
    """ "Otros" puede existir como ingreso y como gasto a la vez."""
    # Arrange
    usuario = await _crear_usuario(db_session)
    await _crear_categoria(db_session, usuario.id, "Otros", TransactionType.EXPENSE)

    # Act
    await _crear_categoria(db_session, usuario.id, "Otros", TransactionType.INCOME)

    # Assert
    total = await db_session.scalar(
        select(func.count()).select_from(CategoryModel).where(CategoryModel.name == "Otros")
    )
    assert total == 2


async def test_no_permite_dos_ocurrencias_para_la_misma_regla_y_fecha(
    db_session: AsyncSession,
) -> None:
    """La garantía dura de idempotencia del job de recurrentes.

    Aunque el job corra dos veces o tenga un bug, la base impide el duplicado.
    """
    # Arrange
    usuario = await _crear_usuario(db_session)
    categoria = await _crear_categoria(db_session, usuario.id)
    regla = await _crear_regla(db_session, usuario.id, categoria.id)
    db_session.add(
        RecurringOccurrenceModel(
            rule_id=regla.id, occurred_on=date(2026, 8, 5), status=OccurrenceStatus.GENERATED
        )
    )
    await db_session.flush()

    # Act
    db_session.add(
        RecurringOccurrenceModel(
            rule_id=regla.id, occurred_on=date(2026, 8, 5), status=OccurrenceStatus.GENERATED
        )
    )

    # Assert
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_no_permite_dos_presupuestos_para_la_misma_categoria_periodo_y_moneda(
    db_session: AsyncSession,
) -> None:
    # Arrange
    usuario = await _crear_usuario(db_session)
    categoria = await _crear_categoria(db_session, usuario.id)
    db_session.add(
        BudgetModel(
            user_id=usuario.id,
            category_id=categoria.id,
            period_month=date(2026, 8, 1),
            amount=Decimal("200000.00"),
        )
    )
    await db_session.flush()

    # Act
    db_session.add(
        BudgetModel(
            user_id=usuario.id,
            category_id=categoria.id,
            period_month=date(2026, 8, 1),
            amount=Decimal("300000.00"),
        )
    )

    # Assert
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


# --- Comportamiento de borrado ---------------------------------------------
async def test_no_se_puede_borrar_una_categoria_con_movimientos(
    db_session: AsyncSession,
) -> None:
    """RESTRICT y no CASCADE: borrar una categoría no puede llevarse el historial."""
    # Arrange
    usuario = await _crear_usuario(db_session)
    categoria = await _crear_categoria(db_session, usuario.id)
    await _crear_movimiento(db_session, usuario.id, categoria.id)

    # Act / Assert
    with pytest.raises(IntegrityError):
        await db_session.execute(delete(CategoryModel).where(CategoryModel.id == categoria.id))
        await db_session.flush()
    await db_session.rollback()


async def test_borrar_un_usuario_arrastra_sus_categorias(db_session: AsyncSession) -> None:
    # Arrange
    usuario = await _crear_usuario(db_session)
    await _crear_categoria(db_session, usuario.id)

    # Act
    await db_session.execute(delete(UserModel).where(UserModel.id == usuario.id))
    await db_session.flush()

    # Assert
    restantes = await db_session.scalar(select(func.count()).select_from(CategoryModel))
    assert restantes == 0


async def test_borrar_un_movimiento_deja_la_ocurrencia_sin_referencia_pero_viva(
    db_session: AsyncSession,
) -> None:
    """El caso que impide que un movimiento salteado reaparezca.

    Si al borrar el movimiento se borrara también la ocurrencia, el job la
    volvería a generar al día siguiente. Por eso es SET NULL y no CASCADE.
    """
    # Arrange
    usuario = await _crear_usuario(db_session)
    categoria = await _crear_categoria(db_session, usuario.id)
    regla = await _crear_regla(db_session, usuario.id, categoria.id)
    movimiento = await _crear_movimiento(
        db_session, usuario.id, categoria.id, recurring_rule_id=regla.id
    )
    ocurrencia = RecurringOccurrenceModel(
        rule_id=regla.id,
        occurred_on=date(2026, 8, 5),
        status=OccurrenceStatus.GENERATED,
        transaction_id=movimiento.id,
    )
    db_session.add(ocurrencia)
    await db_session.flush()

    # Act
    await db_session.execute(delete(TransactionModel).where(TransactionModel.id == movimiento.id))
    await db_session.flush()
    await db_session.refresh(ocurrencia)

    # Assert
    assert ocurrencia.id is not None
    assert ocurrencia.transaction_id is None


async def test_borrar_una_regla_no_borra_los_movimientos_que_genero(
    db_session: AsyncSession,
) -> None:
    """Los movimientos históricos quedan sueltos, no desaparecen."""
    # Arrange
    usuario = await _crear_usuario(db_session)
    categoria = await _crear_categoria(db_session, usuario.id)
    regla = await _crear_regla(db_session, usuario.id, categoria.id)
    movimiento = await _crear_movimiento(
        db_session, usuario.id, categoria.id, recurring_rule_id=regla.id
    )

    # Act
    await db_session.execute(delete(RecurringRuleModel).where(RecurringRuleModel.id == regla.id))
    await db_session.flush()
    await db_session.refresh(movimiento)

    # Assert
    assert movimiento.id is not None
    assert movimiento.recurring_rule_id is None
