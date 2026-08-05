"""Tests de extremo a extremo de los endpoints de autenticación."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.default_categories import CATEGORIAS_POR_DEFECTO
from app.infrastructure.db.models import CategoryModel
from app.infrastructure.security import JwtTokenService
from tests.fakes import FixedClock

pytestmark = pytest.mark.integration

CONTRASENA = "una-contrasena-larga"


@pytest.fixture(autouse=True)
def _base_limpia(db_session: AsyncSession) -> None:
    """Cada test arranca con las tablas vacías."""
    return None


async def _ver_lo_commiteado(session: AsyncSession) -> None:
    """Cierra la transacción del test para ver lo que escribió la API.

    MySQL corre en REPEATABLE READ: sin esto la sesión del test seguiría viendo
    el snapshot tomado antes de la llamada HTTP y las filas nuevas serían
    invisibles.
    """
    await session.rollback()


async def _registrar(
    client: AsyncClient,
    email: str = "damian@ejemplo.com",
    password: str = CONTRASENA,
    nombre: str = "Damián Orsi",
) -> Any:
    return await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": nombre},
    )


async def _login(
    client: AsyncClient, email: str = "damian@ejemplo.com", password: str = CONTRASENA
) -> Any:
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _cuenta_con_sesion(client: AsyncClient, email: str) -> dict[str, Any]:
    """Registra una cuenta e inicia sesión. Devuelve el cuerpo con los tokens."""
    await _registrar(client, email=email)
    respuesta = await _login(client, email=email)
    assert respuesta.status_code == 200, respuesta.text
    return dict(respuesta.json())


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------
class TestRegistro:
    async def test_crea_la_cuenta(self, client: AsyncClient) -> None:
        # Arrange / Act
        respuesta = await _registrar(client)

        # Assert
        assert respuesta.status_code == 201, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["email"] == "damian@ejemplo.com"
        assert cuerpo["is_active"] is True
        assert respuesta.headers["Location"] == "/api/v1/users/me"

    async def test_no_devuelve_el_hash_de_la_contrasena(self, client: AsyncClient) -> None:
        # Arrange / Act
        respuesta = await _registrar(client)

        # Assert
        assert "password" not in respuesta.text
        assert "hash" not in respuesta.text

    async def test_siembra_las_categorias_por_defecto(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        # Arrange / Act
        respuesta = await _registrar(client)
        user_id = respuesta.json()["id"]

        # Assert
        await _ver_lo_commiteado(db_session)
        categorias = (
            await db_session.scalars(select(CategoryModel).where(CategoryModel.user_id == user_id))
        ).all()
        assert len(categorias) == len(CATEGORIAS_POR_DEFECTO)
        assert all(c.is_default for c in categorias)

    async def test_rechaza_un_email_duplicado(self, client: AsyncClient) -> None:
        # Arrange
        await _registrar(client)

        # Act
        respuesta = await _registrar(client)

        # Assert
        assert respuesta.status_code == 409
        assert respuesta.json()["code"] == "email_already_registered"

    async def test_el_email_duplicado_se_detecta_sin_importar_mayusculas(
        self, client: AsyncClient
    ) -> None:
        # Arrange
        await _registrar(client, email="damian@ejemplo.com")

        # Act
        respuesta = await _registrar(client, email="DAMIAN@Ejemplo.COM")

        # Assert
        assert respuesta.status_code == 409

    @pytest.mark.parametrize("password", ["", "corta", "1234567"])
    async def test_rechaza_contrasenas_cortas(self, client: AsyncClient, password: str) -> None:
        # Arrange / Act
        respuesta = await _registrar(client, password=password)

        # Assert
        assert respuesta.status_code == 422
        assert respuesta.json()["code"] == "validation_error"

    @pytest.mark.parametrize("email", ["sinarroba", "@sindominio.com", "a@b", ""])
    async def test_rechaza_emails_invalidos(self, client: AsyncClient, email: str) -> None:
        # Arrange / Act
        respuesta = await _registrar(client, email=email)

        # Assert
        assert respuesta.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
class TestLogin:
    async def test_devuelve_el_par_de_tokens(self, client: AsyncClient) -> None:
        # Arrange
        await _registrar(client)

        # Act
        respuesta = await _login(client)

        # Assert
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["token_type"] == "bearer"
        assert cuerpo["access_token"] and cuerpo["refresh_token"]
        assert cuerpo["expires_in"] == get_settings().access_token_expire_minutes * 60

    async def test_rechaza_la_contrasena_incorrecta(self, client: AsyncClient) -> None:
        # Arrange
        await _registrar(client)

        # Act
        respuesta = await _login(client, password="otra-contrasena-larga")

        # Assert
        assert respuesta.status_code == 401
        assert respuesta.json()["code"] == "invalid_credentials"

    async def test_no_permite_distinguir_email_inexistente_de_contrasena_mala(
        self, client: AsyncClient
    ) -> None:
        """Si las respuestas difirieran, el login sería un oráculo de cuentas."""
        # Arrange
        await _registrar(client, email="existe@ejemplo.com")

        # Act
        con_email_real = await _login(client, email="existe@ejemplo.com", password="mala-mala-mala")
        con_email_falso = await _login(client, email="nadie@ejemplo.com", password="mala-mala-mala")

        # Assert
        assert con_email_real.status_code == con_email_falso.status_code == 401
        assert con_email_real.json() == con_email_falso.json()

    async def test_el_401_trae_el_header_www_authenticate(self, client: AsyncClient) -> None:
        # Arrange / Act
        respuesta = await _login(client, email="nadie@ejemplo.com")

        # Assert
        assert respuesta.headers.get("WWW-Authenticate") == "Bearer"


# ---------------------------------------------------------------------------
# Usuario autenticado
# ---------------------------------------------------------------------------
class TestUsersMe:
    async def test_devuelve_los_datos_de_la_cuenta(self, client: AsyncClient) -> None:
        # Arrange
        tokens = await _cuenta_con_sesion(client, "damian@ejemplo.com")

        # Act
        respuesta = await client.get("/api/v1/users/me", headers=_auth(tokens["access_token"]))

        # Assert
        assert respuesta.status_code == 200
        assert respuesta.json()["email"] == "damian@ejemplo.com"

    async def test_sin_token_devuelve_401(self, client: AsyncClient) -> None:
        # Arrange / Act
        respuesta = await client.get("/api/v1/users/me")

        # Assert
        assert respuesta.status_code == 401
        assert respuesta.json()["code"] == "invalid_token"

    @pytest.mark.parametrize("token", ["basura", "a.b.c", ""])
    async def test_con_un_token_invalido_devuelve_401(
        self, client: AsyncClient, token: str
    ) -> None:
        # Arrange / Act
        respuesta = await client.get("/api/v1/users/me", headers=_auth(token))

        # Assert
        assert respuesta.status_code == 401

    async def test_un_refresh_token_no_sirve_para_autenticar(self, client: AsyncClient) -> None:
        """Dura siete días: si sirviera acá, la vida corta del access no valdría nada."""
        # Arrange
        tokens = await _cuenta_con_sesion(client, "damian@ejemplo.com")

        # Act
        respuesta = await client.get("/api/v1/users/me", headers=_auth(tokens["refresh_token"]))

        # Assert
        assert respuesta.status_code == 401

    async def test_un_access_token_expirado_devuelve_401(self, client: AsyncClient) -> None:
        # Arrange: se emite un token con un reloj atrasado dos horas, así ya
        # nace vencido sin tener que esperar ni manipular el reloj del proceso.
        respuesta = await _registrar(client)
        user_id = respuesta.json()["id"]
        settings = get_settings()
        emisor_viejo = JwtTokenService(
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
            access_ttl=timedelta(minutes=15),
            refresh_ttl=timedelta(days=7),
            clock=FixedClock(datetime.now(UTC) - timedelta(hours=2)),
        )
        expirado = emisor_viejo.create_access_token(user_id).value

        # Act
        respuesta = await client.get("/api/v1/users/me", headers=_auth(expirado))

        # Assert
        assert respuesta.status_code == 401


# ---------------------------------------------------------------------------
# Refresh y logout
# ---------------------------------------------------------------------------
class TestRefresh:
    async def test_devuelve_un_par_nuevo(self, client: AsyncClient) -> None:
        # Arrange
        tokens = await _cuenta_con_sesion(client, "damian@ejemplo.com")

        # Act
        respuesta = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        # Assert
        assert respuesta.status_code == 200
        assert respuesta.json()["refresh_token"] != tokens["refresh_token"]

    async def test_el_refresh_rota_y_el_viejo_deja_de_servir(self, client: AsyncClient) -> None:
        # Arrange
        tokens = await _cuenta_con_sesion(client, "damian@ejemplo.com")
        await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

        # Act
        reintento = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        # Assert
        assert reintento.status_code == 401
        assert reintento.json()["code"] == "invalid_token"

    async def test_el_par_nuevo_sirve_para_autenticar(self, client: AsyncClient) -> None:
        # Arrange
        tokens = await _cuenta_con_sesion(client, "damian@ejemplo.com")

        # Act
        nuevos = (
            await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
            )
        ).json()
        respuesta = await client.get("/api/v1/users/me", headers=_auth(nuevos["access_token"]))

        # Assert
        assert respuesta.status_code == 200

    async def test_un_access_token_no_sirve_para_renovar(self, client: AsyncClient) -> None:
        # Arrange
        tokens = await _cuenta_con_sesion(client, "damian@ejemplo.com")

        # Act
        respuesta = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
        )

        # Assert
        assert respuesta.status_code == 401


class TestLogout:
    async def test_revoca_el_refresh_token(self, client: AsyncClient) -> None:
        # Arrange
        tokens = await _cuenta_con_sesion(client, "damian@ejemplo.com")

        # Act
        salida = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
        )
        reintento = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        # Assert
        assert salida.status_code == 204
        assert reintento.status_code == 401

    async def test_es_idempotente_con_un_token_desconocido(self, client: AsyncClient) -> None:
        """Cerrar sesión nunca falla: si fallara, el front no sabría si limpiar."""
        # Arrange / Act
        respuesta = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": "token-que-no-existe"}
        )

        # Assert
        assert respuesta.status_code == 204


# ---------------------------------------------------------------------------
# Aislamiento entre usuarios
# ---------------------------------------------------------------------------
class TestAislamiento:
    async def test_cada_token_resuelve_a_su_propio_usuario(self, client: AsyncClient) -> None:
        # Arrange
        tokens_a = await _cuenta_con_sesion(client, "a@ejemplo.com")
        tokens_b = await _cuenta_con_sesion(client, "b@ejemplo.com")

        # Act
        como_a = await client.get("/api/v1/users/me", headers=_auth(tokens_a["access_token"]))
        como_b = await client.get("/api/v1/users/me", headers=_auth(tokens_b["access_token"]))

        # Assert
        assert como_a.json()["email"] == "a@ejemplo.com"
        assert como_b.json()["email"] == "b@ejemplo.com"
        assert como_a.json()["id"] != como_b.json()["id"]

    async def test_las_categorias_sembradas_son_de_cada_usuario(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Las categorías por defecto se replican por cuenta, no se comparten."""
        # Arrange
        id_a = (await _registrar(client, email="a@ejemplo.com")).json()["id"]
        id_b = (await _registrar(client, email="b@ejemplo.com")).json()["id"]

        # Act
        await _ver_lo_commiteado(db_session)
        de_a = (
            await db_session.scalars(select(CategoryModel).where(CategoryModel.user_id == id_a))
        ).all()
        de_b = (
            await db_session.scalars(select(CategoryModel).where(CategoryModel.user_id == id_b))
        ).all()

        # Assert
        assert len(de_a) == len(de_b) == len(CATEGORIAS_POR_DEFECTO)
        assert {c.id for c in de_a}.isdisjoint({c.id for c in de_b})

    async def test_el_token_de_uno_no_devuelve_los_datos_del_otro(
        self, client: AsyncClient
    ) -> None:
        """El user_id sale del token y nunca de algo que mande el cliente."""
        # Arrange
        tokens_a = await _cuenta_con_sesion(client, "a@ejemplo.com")
        id_b = (await _registrar(client, email="b@ejemplo.com")).json()["id"]

        # Act: se intenta forzar el id de B por query y por body.
        respuesta = await client.get(
            f"/api/v1/users/me?user_id={id_b}", headers=_auth(tokens_a["access_token"])
        )

        # Assert
        assert respuesta.status_code == 200
        assert respuesta.json()["email"] == "a@ejemplo.com"
        assert respuesta.json()["id"] != id_b
