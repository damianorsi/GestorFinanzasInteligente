"""Dobles de prueba en memoria para los casos de uso.

Son *fakes* y no mocks: tienen una implementación real, simple y sin I/O. Eso
permite testear el comportamiento del caso de uso en vez de verificar qué
métodos llamó, que es lo que termina rompiéndose en cada refactor.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.application.dtos import (
    CategoryTotal,
    CategoryUsage,
    ChatMessage,
    ExtractedReceipt,
    MonthlyTotal,
    Page,
    PaginatedResult,
    PeriodSummary,
    StoredRefreshToken,
    TokenUsage,
    TransactionFilters,
    UserCredentials,
)
from app.domain.entities import (
    Budget,
    BudgetAlert,
    Category,
    RecurringOccurrence,
    RecurringRule,
    Transaction,
    User,
)
from app.domain.enums import (
    AlertStatus,
    AlertType,
    ChatRole,
    OccurrenceStatus,
    ReceiptScanStatus,
    TransactionType,
)
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


class FakeBudgetAlertRepository:
    """Libro de alertas en memoria, con la misma unicidad que la tabla.

    La clave es `(user_id, category_id, period_month, type)`, que es la UNIQUE
    real: así el fake no puede aceptar un duplicado que la base rechazaría.
    """

    def __init__(self) -> None:
        self.alertas: list[BudgetAlert] = []
        # Para el test de aislamiento de fallos: hace explotar el repositorio
        # cuando el job procesa a este usuario.
        self.fallar_para_usuario: int | None = None
        self._siguiente_id = 1

    def _clave(self, alerta: BudgetAlert) -> tuple[int, int, date, AlertType]:
        return (alerta.user_id, alerta.category_id, alerta.period_month, alerta.type)

    async def list_for_user(
        self, user_id: int, status: AlertStatus | None = None
    ) -> list[BudgetAlert]:
        if self.fallar_para_usuario == user_id:
            raise RuntimeError("la base dijo que no")
        return [
            alerta
            for alerta in self.alertas
            if alerta.user_id == user_id and (status is None or alerta.status is status)
        ]

    async def get_for_user(self, user_id: int, alert_id: int) -> BudgetAlert | None:
        return next(
            (a for a in self.alertas if a.id == alert_id and a.user_id == user_id),
            None,
        )

    async def update(self, alert: BudgetAlert) -> BudgetAlert:
        for indice, existente in enumerate(self.alertas):
            if existente.id == alert.id:
                self.alertas[indice] = alert
                return alert
        raise ValueError(f"La alerta {alert.id} no existe.")

    async def create_if_absent(self, alert: BudgetAlert) -> BudgetAlert | None:
        if self.fallar_para_usuario == alert.user_id:
            raise RuntimeError("la base dijo que no")
        if any(self._clave(a) == self._clave(alert) for a in self.alertas):
            return None
        self._siguiente_id += 1
        alert.id = self._siguiente_id
        self.alertas.append(alert)
        return alert

    async def resolve_stale(self, user_id: int, period_month: date, vigentes: set[int]) -> int:
        resueltas = 0
        for alerta in self.alertas:
            if (
                alerta.user_id == user_id
                and alerta.period_month == period_month
                and alerta.status in (AlertStatus.OPEN, AlertStatus.READ)
                and alerta.id not in vigentes
            ):
                alerta.status = AlertStatus.RESOLVED
                resueltas += 1
        return resueltas

    async def list_open_period_ids(self, user_id: int, period_month: date) -> set[int]:
        return {
            alerta.id or 0
            for alerta in self.alertas
            if alerta.user_id == user_id
            and alerta.period_month == period_month
            and alerta.status in (AlertStatus.OPEN, AlertStatus.READ)
        }


class FakeBudgetRepository:
    def __init__(self) -> None:
        self.presupuestos: dict[int, Budget] = {}
        # Lo que devuelve la consulta del job. Por defecto se deriva de los
        # presupuestos cargados.
        self.usuarios_con_presupuesto: list[int] | None = None
        self._siguiente_id = 1

    def agregar(self, budget: Budget) -> Budget:
        """Siembra un presupuesto sin pasar por el caso de uso."""
        if budget.id is None:
            budget.id = self._siguiente_id
            self._siguiente_id += 1
        self.presupuestos[budget.id] = budget
        return budget

    async def list_user_ids_with_budgets(self, period_month: date, currency: str) -> list[int]:
        if self.usuarios_con_presupuesto is not None:
            return self.usuarios_con_presupuesto
        return sorted(
            {
                presupuesto.user_id
                for presupuesto in self.presupuestos.values()
                if presupuesto.period_month == period_month
                and presupuesto.limit.currency == currency
            }
        )

    async def create(self, budget: Budget) -> Budget:
        budget.id = self._siguiente_id
        self._siguiente_id += 1
        self.presupuestos[budget.id] = budget
        return budget

    async def create_many(self, budgets: Sequence[Budget]) -> int:
        for presupuesto in budgets:
            await self.create(presupuesto)
        return len(budgets)

    async def update(self, budget: Budget) -> Budget:
        if budget.id is None or budget.id not in self.presupuestos:
            raise ValueError("El presupuesto no existe.")
        self.presupuestos[budget.id] = budget
        return budget

    async def delete(self, user_id: int, budget_id: int) -> None:
        presupuesto = self.presupuestos.get(budget_id)
        if presupuesto is not None and presupuesto.user_id == user_id:
            del self.presupuestos[budget_id]

    async def get_for_user(self, user_id: int, budget_id: int) -> Budget | None:
        presupuesto = self.presupuestos.get(budget_id)
        if presupuesto is None or presupuesto.user_id != user_id:
            return None
        return presupuesto

    async def list_for_period(
        self, user_id: int, period_month: date, currency: str
    ) -> list[Budget]:
        return [
            presupuesto
            for presupuesto in self.presupuestos.values()
            if presupuesto.user_id == user_id
            and presupuesto.period_month == period_month
            and presupuesto.limit.currency == currency
        ]

    async def exists_for(
        self,
        user_id: int,
        category_id: int,
        period_month: date,
        currency: str,
        exclude_id: int | None = None,
    ) -> bool:
        return any(
            presupuesto.user_id == user_id
            and presupuesto.category_id == category_id
            and presupuesto.period_month == period_month
            and presupuesto.limit.currency == currency
            and presupuesto.id != exclude_id
            for presupuesto in self.presupuestos.values()
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
        self.usuarios_pedidos: list[int] = []

    async def period_summary(
        self, user_id: int, currency: str, date_from: date, date_to: date
    ) -> PeriodSummary:
        self.periodos_pedidos.append((date_from, date_to))
        self.usuarios_pedidos.append(user_id)
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
        self.usuarios_pedidos.append(user_id)
        return self.por_categoria

    async def monthly_totals(
        self, user_id: int, currency: str, date_from: date, date_to: date
    ) -> list[MonthlyTotal]:
        self.periodos_pedidos.append((date_from, date_to))
        self.usuarios_pedidos.append(user_id)
        return self.mensuales


class FakeRecurringOccurrenceRepository:
    """Libro mayor en memoria, con la misma unicidad que la tabla real.

    La clave del diccionario es `(rule_id, occurred_on)`, que es exactamente la
    UNIQUE de `recurring_occurrences`: así el fake no puede aceptar un
    duplicado que la base rechazaría.
    """

    def __init__(self) -> None:
        self.salteadas: list[int] = []
        self.ocurrencias: dict[tuple[int, date], RecurringOccurrence] = {}
        self.movimientos: list[Transaction] = []
        self._siguiente_id = 1

    async def mark_skipped_by_transaction(self, transaction_id: int) -> None:
        self.salteadas.append(transaction_id)
        for ocurrencia in self.ocurrencias.values():
            if ocurrencia.transaction_id == transaction_id:
                ocurrencia.saltear()

    async def resolved_dates(self, rule_id: int) -> set[date]:
        return {fecha for (regla, fecha) in self.ocurrencias if regla == rule_id}

    async def list_for_rule(self, rule_id: int) -> list[RecurringOccurrence]:
        propias = [o for (regla, _), o in self.ocurrencias.items() if regla == rule_id]
        return sorted(propias, key=lambda o: o.occurred_on, reverse=True)

    async def mark_skipped(self, rule_id: int, dates: Iterable[date]) -> int:
        pendientes = set(dates) - await self.resolved_dates(rule_id)
        for fecha in sorted(pendientes):
            self.ocurrencias[(rule_id, fecha)] = RecurringOccurrence(
                id=self._nuevo_id(),
                rule_id=rule_id,
                occurred_on=fecha,
                status=OccurrenceStatus.SKIPPED,
            )
        return len(pendientes)

    async def register_generated(self, transaction: Transaction, occurred_on: date) -> bool:
        clave = (transaction.recurring_rule_id or 0, occurred_on)
        if clave in self.ocurrencias:
            return False

        transaction.id = self._nuevo_id()
        self.movimientos.append(transaction)
        self.ocurrencias[clave] = RecurringOccurrence(
            id=self._nuevo_id(),
            rule_id=transaction.recurring_rule_id or 0,
            occurred_on=occurred_on,
            status=OccurrenceStatus.GENERATED,
            transaction_id=transaction.id,
        )
        return True

    def _nuevo_id(self) -> int:
        self._siguiente_id += 1
        return self._siguiente_id


class FakeRecurringRuleRepository:
    def __init__(self) -> None:
        self.reglas: list[RecurringRule] = []
        self._siguiente_id = 1

    def agregar(self, regla: RecurringRule) -> RecurringRule:
        """Siembra una regla sin pasar por el caso de uso."""
        if regla.id is None:
            self._siguiente_id += 1
            regla.id = self._siguiente_id
        self.reglas.append(regla)
        return regla

    async def create(self, rule: RecurringRule) -> RecurringRule:
        return self.agregar(rule)

    async def update(self, rule: RecurringRule) -> RecurringRule:
        for indice, existente in enumerate(self.reglas):
            if existente.id == rule.id:
                self.reglas[indice] = rule
                return rule
        raise ValueError(f"La regla {rule.id} no existe.")

    async def delete(self, user_id: int, rule_id: int) -> None:
        self.reglas = [
            regla for regla in self.reglas if not (regla.id == rule_id and regla.user_id == user_id)
        ]

    async def get_for_user(self, user_id: int, rule_id: int) -> RecurringRule | None:
        return next(
            (r for r in self.reglas if r.id == rule_id and r.user_id == user_id),
            None,
        )

    async def list_for_user(
        self, user_id: int, currency: str, is_active: bool | None = None
    ) -> list[RecurringRule]:
        return [
            regla
            for regla in self.reglas
            if regla.user_id == user_id
            and regla.currency == currency
            and (is_active is None or regla.is_active is is_active)
        ]

    async def list_active_for_user(self, user_id: int, currency: str) -> list[RecurringRule]:
        return await self.list_for_user(user_id, currency, is_active=True)

    async def list_all_active(self) -> list[RecurringRule]:
        return [regla for regla in self.reglas if regla.is_active]

    async def deactivate(self, rule_id: int) -> None:
        for regla in self.reglas:
            if regla.id == rule_id:
                regla.is_active = False


class FakeChatRepository:
    """Historial y telemetría del asistente, en memoria.

    Guarda los mensajes de todos los usuarios en una sola lista y filtra al
    leer, igual que la tabla real: así un test de aislamiento falla si el
    filtrado se cae, en vez de pasar porque cada usuario tenía su diccionario.
    """

    def __init__(self, ahora: datetime | None = None) -> None:
        self.mensajes: list[tuple[int, str, ChatMessage]] = []
        self.consumos: list[tuple[int, str, TokenUsage, int]] = []
        # Público para que un test pueda mover el reloj y dejar mensajes viejos.
        self.ahora = ahora or datetime(2026, 8, 5, 12, 0, 0)

    async def save_message(
        self, user_id: int, conversation_id: str, role: ChatRole, content: str
    ) -> None:
        mensaje = ChatMessage(role=role, content=content, created_at=self.ahora)
        self.mensajes.append((user_id, conversation_id, mensaje))

    async def history(self, user_id: int, conversation_id: str, limit: int) -> list[ChatMessage]:
        propios = [
            mensaje
            for uid, cid, mensaje in self.mensajes
            if uid == user_id and cid == conversation_id
        ]
        return propios[-limit:]

    async def count_user_messages_since(self, user_id: int, since: datetime) -> int:
        return sum(
            1
            for uid, _, mensaje in self.mensajes
            if uid == user_id and mensaje.role is ChatRole.USER and mensaje.created_at >= since
        )

    async def save_usage(
        self, user_id: int, conversation_id: str, usage: TokenUsage, latency_ms: int
    ) -> None:
        self.consumos.append((user_id, conversation_id, usage, latency_ms))


@dataclass
class LecturaGuardada:
    """Lo que el repositorio de tickets persiste.

    **No tiene campo para la imagen**, igual que la tabla real: la foto se
    procesa en memoria y se descarta (docs/PROMPT.md §21.1).
    """

    user_id: int
    status: ReceiptScanStatus
    amount: Decimal | None
    occurred_on: date | None
    merchant: str | None
    category_id: int | None
    model: str
    latency_ms: int
    created_at: datetime


class FakeReceiptScanRepository:
    def __init__(self, ahora: datetime | None = None) -> None:
        self.lecturas: list[LecturaGuardada] = []
        self.duplicados: list[int] = []
        # Movimientos que este repositorio haya creado. Siempre vacío: el
        # caso de uso no crea ninguno, y el test lo verifica.
        self.movimientos_creados: list[int] = []
        self.ahora = ahora or datetime(2026, 8, 5, 12, 0, 0)
        self._siguiente_id = 1

    async def save(
        self,
        user_id: int,
        extracted: ExtractedReceipt,
        category_id: int | None,
        model: str,
        total_tokens: int,
        latency_ms: int,
    ) -> int:
        self.lecturas.append(
            LecturaGuardada(
                user_id=user_id,
                status=ReceiptScanStatus.EXTRACTED,
                amount=extracted.amount,
                occurred_on=extracted.occurred_on,
                merchant=extracted.merchant,
                category_id=category_id,
                model=model,
                latency_ms=latency_ms,
                created_at=self.ahora,
            )
        )
        self._siguiente_id += 1
        return self._siguiente_id

    async def save_failure(self, user_id: int, model: str, latency_ms: int) -> None:
        self.lecturas.append(
            LecturaGuardada(
                user_id=user_id,
                status=ReceiptScanStatus.FAILED,
                amount=None,
                occurred_on=None,
                merchant=None,
                category_id=None,
                model=model,
                latency_ms=latency_ms,
                created_at=self.ahora,
            )
        )

    async def count_since(self, user_id: int, since: datetime) -> int:
        # Cada lectura queda sellada con el `ahora` del momento, igual que el
        # `created_at` de la tabla. El test mueve `ahora` para simular el paso
        # del tiempo y así el filtro por hora se ejercita de verdad.
        return sum(
            1
            for lectura in self.lecturas
            if lectura.user_id == user_id and lectura.created_at >= since
        )

    async def find_possible_duplicates(
        self, user_id: int, amount: Decimal, occurred_on: date, currency: str
    ) -> list[int]:
        return list(self.duplicados)


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
