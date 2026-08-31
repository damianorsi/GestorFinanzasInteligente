"""Tests de extremo a extremo de las reglas recurrentes.

Incluye el job corriendo contra MySQL: la idempotencia se apoya en la UNIQUE
`(rule_id, occurred_on)`, y eso solo se prueba contra la base real.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.recurring import GenerateRecurringTransactions
from app.infrastructure.clock import get_clock
from app.infrastructure.db.models import RecurringOccurrenceModel, TransactionModel
from app.infrastructure.db.repositories import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyRecurringOccurrenceRepository,
    SqlAlchemyRecurringRuleRepository,
)
from app.infrastructure.db.session import get_session_factory
from tests.helpers import CuentaDePrueba, crear_cuenta

pytestmark = pytest.mark.integration

RUTA = "/api/v1/recurring-rules"
CATEGORIAS = "/api/v1/categories"
TRANSACCIONES = "/api/v1/transactions"

HOY = date(2026, 8, 5)
CATCHUP = 90


@pytest.fixture(autouse=True)
def _base_limpia(db_session: AsyncSession) -> None:
    return None


@pytest.fixture
async def cuenta(client: AsyncClient) -> CuentaDePrueba:
    return await crear_cuenta(client, "damian@ejemplo.com")


@pytest.fixture
async def ajena(client: AsyncClient) -> CuentaDePrueba:
    return await crear_cuenta(client, "otra@ejemplo.com")


async def _categoria_id(client: AsyncClient, cuenta: CuentaDePrueba, nombre: str) -> int:
    listado = (await client.get(CATEGORIAS, headers=cuenta.headers)).json()
    return next(c["id"] for c in listado if c["name"] == nombre)


async def _crear_regla(
    client: AsyncClient,
    cuenta: CuentaDePrueba,
    *,
    categoria: str = "Servicios",
    tipo: str = "EXPENSE",
    monto: str = "45000.00",
    frecuencia: str = "MONTHLY",
    starts_on: str = "2026-06-10",
    day_of_month: int | None = 10,
    day_of_week: int | None = None,
    ends_on: str | None = None,
    descripcion: str = "Alquiler",
) -> dict[str, object]:
    cuerpo: dict[str, object] = {
        "category_id": await _categoria_id(client, cuenta, categoria),
        "type": tipo,
        "amount": monto,
        "frequency": frecuencia,
        "starts_on": starts_on,
        "description": descripcion,
    }
    if day_of_month is not None:
        cuerpo["day_of_month"] = day_of_month
    if day_of_week is not None:
        cuerpo["day_of_week"] = day_of_week
    if ends_on is not None:
        cuerpo["ends_on"] = ends_on

    respuesta = await client.post(RUTA, headers=cuenta.headers, json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return dict(respuesta.json())


@asynccontextmanager
async def _job(catchup: int = CATCHUP) -> AsyncIterator[GenerateRecurringTransactions]:
    """Arma el job sobre una sesión propia.

    Sesión nueva y no la del fixture porque los datos se siembran por HTTP: con
    REPEATABLE READ, una sesión que ya leyó no vería lo comiteado después.
    """
    async with get_session_factory()() as session:
        yield GenerateRecurringTransactions(
            rules=SqlAlchemyRecurringRuleRepository(session),
            occurrences=SqlAlchemyRecurringOccurrenceRepository(session),
            categories=SqlAlchemyCategoryRepository(session),
            catchup_max_days=catchup,
        )
        await session.commit()


async def _contar_movimientos(rule_id: int) -> int:
    async with get_session_factory()() as session:
        total = await session.scalar(
            select(func.count())
            .select_from(TransactionModel)
            .where(TransactionModel.recurring_rule_id == rule_id)
        )
        return int(total or 0)


async def _ocurrencias(rule_id: int) -> list[RecurringOccurrenceModel]:
    async with get_session_factory()() as session:
        filas = await session.scalars(
            select(RecurringOccurrenceModel)
            .where(RecurringOccurrenceModel.rule_id == rule_id)
            .order_by(RecurringOccurrenceModel.occurred_on)
        )
        return list(filas.all())


class TestAlta:
    async def test_crea_la_regla_con_location(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Act
        respuesta = await client.post(
            RUTA,
            headers=cuenta.headers,
            json={
                "category_id": await _categoria_id(client, cuenta, "Servicios"),
                "type": "EXPENSE",
                "amount": "45000.00",
                "frequency": "MONTHLY",
                "starts_on": "2026-06-10",
                "day_of_month": 10,
                "description": "Alquiler",
            },
        )

        # Assert
        assert respuesta.status_code == 201, respuesta.text
        assert respuesta.headers["Location"].startswith("/api/v1/recurring-rules/")
        cuerpo = respuesta.json()
        assert cuerpo["amount"] == "45000.00"
        assert cuerpo["currency"] == "ARS"
        assert cuerpo["is_active"] is True

    async def test_devuelve_las_proximas_tres_fechas(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Act
        regla = await _crear_regla(client, cuenta)

        # Assert: es el feedback inmediato de que la regla quedó bien.
        assert len(regla["next_dates"]) == 3  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("descripcion", "cambios"),
        [
            ("mensual sin day_of_month", {"day_of_month": None}),
            ("semanal con day_of_month", {"frequency": "WEEKLY", "day_of_month": 10}),
            ("diaria con day_of_month", {"frequency": "DAILY", "day_of_month": 10}),
            ("monto cero", {"amount": "0.00"}),
            ("fin antes del inicio", {"ends_on": "2026-01-01"}),
        ],
    )
    async def test_rechaza_configuraciones_incoherentes(
        self,
        client: AsyncClient,
        cuenta: CuentaDePrueba,
        descripcion: str,
        cambios: dict[str, object],
    ) -> None:
        # Arrange
        cuerpo: dict[str, object] = {
            "category_id": await _categoria_id(client, cuenta, "Servicios"),
            "type": "EXPENSE",
            "amount": "45000.00",
            "frequency": "MONTHLY",
            "starts_on": "2026-06-10",
            "day_of_month": 10,
        }
        cuerpo.update(cambios)
        if cuerpo.get("day_of_month") is None:
            cuerpo.pop("day_of_month", None)

        # Act
        respuesta = await client.post(RUTA, headers=cuenta.headers, json=cuerpo)

        # Assert
        assert respuesta.status_code == 422, f"{descripcion}: {respuesta.text}"

    async def test_rechaza_una_categoria_del_otro_tipo(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Act
        respuesta = await client.post(
            RUTA,
            headers=cuenta.headers,
            json={
                "category_id": await _categoria_id(client, cuenta, "Sueldo"),
                "type": "EXPENSE",
                "amount": "45000.00",
                "frequency": "MONTHLY",
                "starts_on": "2026-06-10",
                "day_of_month": 10,
            },
        )

        # Assert
        assert respuesta.status_code == 422
        assert respuesta.json()["code"] == "invalid_reference"


class TestEdicionYBorrado:
    async def test_pausa_y_reactiva(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        regla = await _crear_regla(client, cuenta)

        # Act
        pausada = await client.patch(
            f"{RUTA}/{regla['id']}", headers=cuenta.headers, json={"is_active": False}
        )
        reactivada = await client.patch(
            f"{RUTA}/{regla['id']}", headers=cuenta.headers, json={"is_active": True}
        )

        # Assert
        assert pausada.json()["is_active"] is False
        assert reactivada.json()["is_active"] is True

    async def test_una_regla_pausada_no_proyecta_fechas(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        regla = await _crear_regla(client, cuenta)

        # Act
        pausada = await client.patch(
            f"{RUTA}/{regla['id']}", headers=cuenta.headers, json={"is_active": False}
        )

        # Assert
        assert pausada.json()["next_dates"] == []

    async def test_borrar_la_regla_no_borra_los_movimientos_generados(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        regla = await _crear_regla(client, cuenta)
        async with _job() as job:
            await job.execute(HOY)
        assert await _contar_movimientos(int(regla["id"])) == 2  # type: ignore[arg-type]

        # Act
        borrado = await client.delete(f"{RUTA}/{regla['id']}", headers=cuenta.headers)

        # Assert: quedan como movimientos sueltos. Borrar una regla es dejar de
        # generar hacia adelante, no reescribir el historial.
        assert borrado.status_code == 204
        listado = (await client.get(TRANSACCIONES, headers=cuenta.headers)).json()
        assert listado["totalCount"] == 2
        assert all(m["is_recurring"] is False for m in listado["entries"])

    async def test_no_deja_tocar_una_regla_ajena(
        self, client: AsyncClient, cuenta: CuentaDePrueba, ajena: CuentaDePrueba
    ) -> None:
        # Arrange
        regla = await _crear_regla(client, cuenta)

        # Act
        respuesta = await client.patch(
            f"{RUTA}/{regla['id']}", headers=ajena.headers, json={"is_active": False}
        )

        # Assert: 404 y no 403, para no confirmar que el id existe.
        assert respuesta.status_code == 404


class TestListado:
    async def test_filtra_por_estado(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        activa = await _crear_regla(client, cuenta, day_of_month=10)
        pausada = await _crear_regla(client, cuenta, day_of_month=20)
        await client.patch(
            f"{RUTA}/{pausada['id']}", headers=cuenta.headers, json={"is_active": False}
        )

        # Act
        respuesta = await client.get(RUTA, headers=cuenta.headers, params={"is_active": True})

        # Assert
        assert [r["id"] for r in respuesta.json()] == [activa["id"]]

    async def test_no_devuelve_reglas_ajenas(
        self, client: AsyncClient, cuenta: CuentaDePrueba, ajena: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_regla(client, cuenta)

        # Act
        respuesta = await client.get(RUTA, headers=ajena.headers)

        # Assert
        assert respuesta.json() == []


class TestProyeccion:
    async def test_devuelve_los_vencimientos_futuros(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange: día 28, para que caiga adelante de cualquier "hoy" temprano.
        await _crear_regla(client, cuenta, day_of_month=28, starts_on="2026-01-28")

        # Act
        respuesta = await client.get(
            RUTA + "/upcoming", headers=cuenta.headers, params={"days": 365}
        )

        # Assert
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert len(cuerpo["entries"]) >= 1
        assert cuerpo["currency"] == "ARS"
        # La proyección arranca mañana: lo de hoy ya lo materializó el job.
        assert all(e["due_on"] >= cuerpo["date_from"] for e in cuerpo["entries"])

    async def test_las_proyecciones_no_entran_en_el_balance(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        await _crear_regla(client, cuenta, day_of_month=28, starts_on="2026-01-28")

        # Act
        reportes = await client.get(
            "/api/v1/reports/summary",
            headers=cuenta.headers,
            params={"date_from": "2026-01-01", "date_to": "2027-12-31"},
        )

        # Assert: el balance solo cuenta movimientos reales. Si contara las
        # proyecciones, mostraría plata que todavía no se movió.
        assert reportes.json()["expense"] == "0.00"

    async def test_rechaza_una_ventana_fuera_de_rango(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Act
        respuesta = await client.get(RUTA + "/upcoming", headers=cuenta.headers, params={"days": 0})

        # Assert
        assert respuesta.status_code == 422


class TestJobContraLaBase:
    async def test_genera_los_movimientos_pendientes(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        regla = await _crear_regla(client, cuenta, starts_on="2026-06-10", day_of_month=10)

        # Act
        async with _job() as job:
            resultado = await job.execute(HOY)

        # Assert: junio y julio; el 10 de agosto todavía no llegó.
        assert resultado.generated == 2
        listado = (await client.get(TRANSACCIONES, headers=cuenta.headers)).json()
        assert [m["occurred_on"] for m in listado["entries"]] == ["2026-07-10", "2026-06-10"]
        assert all(m["is_recurring"] is True for m in listado["entries"])
        assert await _contar_movimientos(int(regla["id"])) == 2  # type: ignore[arg-type]

    async def test_correrlo_tres_veces_no_duplica_nada(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        regla = await _crear_regla(client, cuenta, starts_on="2026-06-10")

        # Act
        for _ in range(3):
            async with _job() as job:
                await job.execute(HOY)

        # Assert: la UNIQUE (rule_id, occurred_on) es la garantía dura.
        assert await _contar_movimientos(int(regla["id"])) == 2  # type: ignore[arg-type]

    async def test_nunca_genera_futuro(self, client: AsyncClient, cuenta: CuentaDePrueba) -> None:
        # Arrange
        await _crear_regla(
            client, cuenta, frecuencia="DAILY", starts_on="2026-08-01", day_of_month=None
        )

        # Act
        async with _job() as job:
            await job.execute(HOY)

        # Assert
        listado = (await client.get(TRANSACCIONES, headers=cuenta.headers)).json()
        assert max(m["occurred_on"] for m in listado["entries"]) == HOY.isoformat()

    async def test_un_movimiento_borrado_no_reaparece(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange: se genera, y después se borra el de julio a mano.
        regla = await _crear_regla(client, cuenta, starts_on="2026-06-10")
        async with _job() as job:
            await job.execute(HOY)

        listado = (await client.get(TRANSACCIONES, headers=cuenta.headers)).json()
        julio = next(m for m in listado["entries"] if m["occurred_on"] == "2026-07-10")
        borrado = await client.delete(f"{TRANSACCIONES}/{julio['id']}", headers=cuenta.headers)
        assert borrado.status_code == 204

        # Act
        async with _job() as job:
            await job.execute(HOY)

        # Assert: si el alquiler borrado reapareciera al otro día, el libro
        # mayor estaría mal implementado. Es el bug más probable de la feature.
        assert await _contar_movimientos(int(regla["id"])) == 1  # type: ignore[arg-type]
        estados = {o.occurred_on: o.status.value for o in await _ocurrencias(int(regla["id"]))}  # type: ignore[arg-type]
        assert estados[date(2026, 7, 10)] == "SKIPPED"
        assert estados[date(2026, 6, 10)] == "GENERATED"

    async def test_reactivar_no_dispara_backfill(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange: se crea pausada desde enero y se reactiva hoy.
        regla = await _crear_regla(client, cuenta, starts_on="2026-01-10")
        await client.patch(
            f"{RUTA}/{regla['id']}", headers=cuenta.headers, json={"is_active": False}
        )
        await client.patch(
            f"{RUTA}/{regla['id']}", headers=cuenta.headers, json={"is_active": True}
        )

        # Act: el job corre con el MISMO hoy que usó la reactivación, que fue
        # por la API y por lo tanto con el reloj real. Con el `HOY` fijo de los
        # otros tests, las dos ventanas de catch-up quedan ancladas en fechas
        # distintas: al alejarse el reloj real de esa constante dejan de
        # solaparse, y aparece un mes que el job genera porque la reactivación
        # nunca lo alcanzó a marcar.
        async with _job() as job:
            await job.execute(get_clock().today())

        # Assert: pausar es decidir no generar, no diferir. Sin esto, reactivar
        # inyectaría de golpe todos los meses de la pausa.
        assert await _contar_movimientos(int(regla["id"])) == 0  # type: ignore[arg-type]

    async def test_el_catchup_recorta_la_ventana(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange: una regla diaria arrancada 200 días atrás.
        inicio = (HOY - timedelta(days=200)).isoformat()
        regla = await _crear_regla(
            client, cuenta, frecuencia="DAILY", starts_on=inicio, day_of_month=None
        )

        # Act
        async with _job(catchup=10) as job:
            await job.execute(HOY)

        # Assert: la ventana es [hoy-10, hoy], o sea 11 días.
        assert await _contar_movimientos(int(regla["id"])) == 11  # type: ignore[arg-type]

    async def test_el_historial_muestra_lo_generado(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        regla = await _crear_regla(client, cuenta, starts_on="2026-06-10")
        async with _job() as job:
            await job.execute(HOY)

        # Act
        respuesta = await client.get(f"{RUTA}/{regla['id']}/occurrences", headers=cuenta.headers)

        # Assert: de la más reciente a la más vieja.
        cuerpo = respuesta.json()
        assert [o["occurred_on"] for o in cuerpo] == ["2026-07-10", "2026-06-10"]
        assert all(o["status"] == "GENERATED" for o in cuerpo)
        assert all(o["transaction_id"] is not None for o in cuerpo)

    async def test_no_deja_leer_el_historial_de_una_regla_ajena(
        self, client: AsyncClient, cuenta: CuentaDePrueba, ajena: CuentaDePrueba
    ) -> None:
        # Arrange
        regla = await _crear_regla(client, cuenta)

        # Act
        respuesta = await client.get(f"{RUTA}/{regla['id']}/occurrences", headers=ajena.headers)

        # Assert
        assert respuesta.status_code == 404


class TestCategoriasEnUso:
    async def test_no_deja_borrar_una_categoria_con_reglas(
        self, client: AsyncClient, cuenta: CuentaDePrueba
    ) -> None:
        # Arrange
        categoria = await _categoria_id(client, cuenta, "Servicios")
        await _crear_regla(client, cuenta)

        # Act
        respuesta = await client.delete(f"{CATEGORIAS}/{categoria}", headers=cuenta.headers)

        # Assert: el 409 enumera qué está bloqueando el borrado.
        assert respuesta.status_code == 409
        assert "regla recurrente" in respuesta.json()["message"]


class TestSalud:
    async def test_informa_el_estado_del_scheduler(self, client: AsyncClient) -> None:
        # Act
        respuesta = await client.get("/health")

        # Assert: en tests el scheduler no arranca a propósito, para que un job
        # disparándose en medio de la suite no genere movimientos que nadie pidió.
        cuerpo = respuesta.json()
        assert cuerpo["scheduler"] == "disabled"
        assert cuerpo["scheduler_last_run"] is None
