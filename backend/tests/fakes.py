"""Dobles de prueba en memoria para los casos de uso.

Son *fakes* y no mocks: tienen una implementación real, simple y sin I/O. Eso
permite testear el comportamiento del caso de uso en vez de verificar qué
métodos llamó, que es lo que termina rompiéndose en cada refactor.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

from app.application.dtos import (
    CategoryTotal,
    CategoryUsage,
    MonthlyTotal,
    Page,
    PaginatedResult,
    PeriodSummary,
    StoredRefreshToken,
    TransactionFilters,
    UserCredentials,
)
from app.domain.entities import Category, Transaction, User
from app.domain.enums import TransactionType
from app.domain.value_objects import Money


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
        self.usos: dict[int, CategoryUsage] = {}
        self._siguiente_id = 1

    def _asignar_id(self, categoria: Category) -> Category:
        if categoria.id is None:
            categoria.id = self._siguiente_id
            self._siguiente_id += 1
        return categoria

    async def create_many(self, categories: Sequence[Category]) -> None:
        for categoria in categories:
            self.categorias.append(self._asignar_id(categoria))

    async def create(self, category: Category) -> Category:
        self.categorias.append(self._asignar_id(category))
        return category

    async def update(self, category: Category) -> Category:
        for indice, existente in enumerate(self.categorias):
            if existente.id == category.id:
                self.categorias[indice] = category
                return category
        raise ValueError("La categoría no existe.")

    async def delete(self, user_id: int, category_id: int) -> None:
        self.categorias = [
            c for c in self.categorias if not (c.id == category_id and c.user_id == user_id)
        ]

    async def count_for_user(self, user_id: int) -> int:
        return sum(1 for c in self.categorias if c.user_id == user_id)

    async def list_for_user(
        self, user_id: int, type: TransactionType | None = None
    ) -> list[Category]:
        propias = [c for c in self.categorias if c.user_id == user_id]
        if type is not None:
            propias = [c for c in propias if c.type is type]
        # Mismo criterio que el repositorio real: ingresos antes que gastos.
        # Ordenar por `type.value` daría el orden inverso y los tests unitarios
        # estarían validando algo distinto de lo que hace producción.
        return sorted(
            propias,
            key=lambda c: (0 if c.type is TransactionType.INCOME else 1, c.name),
        )

    async def get_for_user(self, user_id: int, category_id: int) -> Category | None:
        for categoria in self.categorias:
            if categoria.id == category_id and categoria.user_id == user_id:
                return categoria
        return None

    async def exists_with_name(
        self,
        user_id: int,
        name: str,
        type: TransactionType,
        exclude_id: int | None = None,
    ) -> bool:
        return any(
            c.user_id == user_id and c.name == name and c.type is type and c.id != exclude_id
            for c in self.categorias
        )

    async def count_usages(self, category_id: int) -> CategoryUsage:
        return self.usos.get(category_id, CategoryUsage(0, 0, 0))


class FakeTransactionRepository:
    """Fake deliberadamente simple.

    `search` NO reimplementa los filtros, el orden ni la paginación: eso es
    responsabilidad del repositorio real y se prueba contra MySQL en los tests
    de integración. Un fake que duplicara esa lógica podría divergir del SQL y
    dejar pasar tests que en producción fallan.
    """

    def __init__(self) -> None:
        self.movimientos: dict[int, Transaction] = {}
        self._siguiente_id = 1

    async def create(self, transaction: Transaction) -> Transaction:
        transaction.id = self._siguiente_id
        self._siguiente_id += 1
        self.movimientos[transaction.id] = transaction
        return transaction

    async def update(self, transaction: Transaction) -> Transaction:
        if transaction.id is None or transaction.id not in self.movimientos:
            raise ValueError("El movimiento no existe.")
        self.movimientos[transaction.id] = transaction
        return transaction

    async def delete(self, user_id: int, transaction_id: int) -> None:
        movimiento = self.movimientos.get(transaction_id)
        if movimiento is not None and movimiento.user_id == user_id:
            del self.movimientos[transaction_id]

    async def get_for_user(self, user_id: int, transaction_id: int) -> Transaction | None:
        movimiento = self.movimientos.get(transaction_id)
        if movimiento is None or movimiento.user_id != user_id:
            return None
        return movimiento

    async def search(
        self, user_id: int, filters: TransactionFilters, page: Page
    ) -> PaginatedResult[Transaction]:
        propios = [
            m
            for m in self.movimientos.values()
            if m.user_id == user_id and m.money.currency == filters.currency
        ]
        ventana = propios[page.offset : page.offset + page.limit]
        return PaginatedResult(
            entries=ventana, offset=page.offset, limit=page.limit, total_count=len(propios)
        )


class FakeReportRepository:
    """Devuelve lo que se le cargue.

    No agrega nada: las agregaciones son SQL puro y se prueban contra MySQL.
    Acá solo interesa lo que el caso de uso hace *con* los totales, que es
    resolver el período, validar la moneda y rellenar los meses vacíos.
    """

    def __init__(self) -> None:
        self.resumen: PeriodSummary | None = None
        self.por_categoria: list[CategoryTotal] = []
        self.mensuales: list[MonthlyTotal] = []
        self.periodos_pedidos: list[tuple[date, date]] = []

    async def period_summary(
        self, user_id: int, currency: str, date_from: date, date_to: date
    ) -> PeriodSummary:
        self.periodos_pedidos.append((date_from, date_to))
        if self.resumen is not None:
            return self.resumen
        cero = Money.zero(currency)
        return PeriodSummary(
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            income=cero,
            expense=cero,
        )

    async def totals_by_category(
        self,
        user_id: int,
        currency: str,
        date_from: date,
        date_to: date,
        type: TransactionType | None = None,
    ) -> list[CategoryTotal]:
        self.periodos_pedidos.append((date_from, date_to))
        return self.por_categoria

    async def monthly_totals(
        self, user_id: int, currency: str, date_from: date, date_to: date
    ) -> list[MonthlyTotal]:
        self.periodos_pedidos.append((date_from, date_to))
        return self.mensuales


class FakeRecurringOccurrenceRepository:
    def __init__(self) -> None:
        self.salteadas: list[int] = []

    async def mark_skipped_by_transaction(self, transaction_id: int) -> None:
        self.salteadas.append(transaction_id)


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
