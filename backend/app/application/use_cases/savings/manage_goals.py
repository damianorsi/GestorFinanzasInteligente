"""Casos de uso del ABM de metas de ahorro (docs/PROMPT.md §21.3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.application.exceptions import (
    DuplicateResourceError,
    ResourceNotFoundError,
    UnsupportedCurrencyError,
)
from app.application.ports import Clock, SavingsGoalRepository
from app.domain.entities import SavingsGoal
from app.domain.value_objects import Money


class _MetasDelUsuario:
    """Base con las validaciones compartidas."""

    def __init__(
        self,
        goals: SavingsGoalRepository,
        clock: Clock,
        supported_currencies: frozenset[str],
        default_currency: str,
    ) -> None:
        self._goals = goals
        self._clock = clock
        self._supported_currencies = supported_currencies
        self._default_currency = default_currency

    def _resolver_moneda(self, currency: str | None) -> str:
        moneda = (currency or self._default_currency).upper()
        if moneda not in self._supported_currencies:
            habilitadas = ", ".join(sorted(self._supported_currencies))
            raise UnsupportedCurrencyError(
                f"La moneda {moneda} no está habilitada. Disponibles: {habilitadas}."
            )
        return moneda

    async def _obtener_propia(self, user_id: int, goal_id: int) -> SavingsGoal:
        meta = await self._goals.get_for_user(user_id, goal_id)
        if meta is None:
            raise ResourceNotFoundError("La meta no existe.")
        return meta

    async def _exigir_nombre_libre(
        self, user_id: int, name: str, exclude_id: int | None = None
    ) -> None:
        if await self._goals.exists_with_name(user_id, name.strip(), exclude_id):
            raise DuplicateResourceError(f"Ya tenés una meta llamada «{name.strip()}».")


class ListSavingsGoals(_MetasDelUsuario):
    async def execute(
        self, user_id: int, currency: str | None = None, only_active: bool = True
    ) -> list[SavingsGoal]:
        moneda = self._resolver_moneda(currency)
        return await self._goals.list_for_user(user_id, moneda, only_active)


class CreateSavingsGoal(_MetasDelUsuario):
    async def execute(
        self,
        user_id: int,
        name: str,
        target_amount: Decimal,
        starts_on: date | None = None,
        target_date: date | None = None,
        currency: str | None = None,
    ) -> SavingsGoal:
        moneda = self._resolver_moneda(currency)
        await self._exigir_nombre_libre(user_id, name)
        # Sin fecha de inicio, la meta arranca hoy y no retroactivamente: contar
        # como ahorro un balance que la persona ya gastó inflaría el avance
        # desde el minuto cero.
        meta = SavingsGoal(
            user_id=user_id,
            name=name,
            target=Money(target_amount, moneda),
            starts_on=starts_on or self._clock.today(),
            target_date=target_date,
        )
        return await self._goals.create(meta)


class UpdateSavingsGoal(_MetasDelUsuario):
    async def execute(
        self,
        user_id: int,
        goal_id: int,
        *,
        name: str | None = None,
        target_amount: Decimal | None = None,
        starts_on: date | None = None,
        target_date: date | None = None,
        is_active: bool | None = None,
        limpiar_target_date: bool = False,
    ) -> SavingsGoal:
        """`limpiar_target_date` saca la fecha objetivo.

        Hace falta un flag aparte porque `target_date=None` ya significa «no lo
        toques»: sin él, una meta con fecha no podría volver a no tenerla.
        """
        meta = await self._obtener_propia(user_id, goal_id)

        if name is not None:
            await self._exigir_nombre_libre(user_id, name, exclude_id=goal_id)

        if limpiar_target_date:
            fecha_objetivo = None
        else:
            fecha_objetivo = meta.target_date if target_date is None else target_date

        # Se rearma la entidad en vez de mutarla campo por campo para que el
        # `__post_init__` valide la combinación resultante: mover solo el
        # inicio puede dejarlo después de la fecha objetivo, y mutando eso no
        # se detecta.
        actualizada = SavingsGoal(
            id=meta.id,
            user_id=meta.user_id,
            name=meta.name if name is None else name,
            target=(
                meta.target if target_amount is None else Money(target_amount, meta.target.currency)
            ),
            starts_on=meta.starts_on if starts_on is None else starts_on,
            target_date=fecha_objetivo,
            is_active=meta.is_active if is_active is None else is_active,
        )
        return await self._goals.update(actualizada)


class DeleteSavingsGoal(_MetasDelUsuario):
    async def execute(self, user_id: int, goal_id: int) -> None:
        await self._obtener_propia(user_id, goal_id)
        await self._goals.delete(user_id, goal_id)
