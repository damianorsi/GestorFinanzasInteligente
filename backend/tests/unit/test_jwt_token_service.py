"""Tests de la emisión y validación de JWT."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.application.dtos import TokenType
from app.application.exceptions import InvalidTokenError
from app.infrastructure.security import JwtTokenService
from tests.fakes import FixedClock

SECRETO = "secreto-solo-para-tests-con-largo-suficiente"
AHORA = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(AHORA)


@pytest.fixture
def service(clock: FixedClock) -> JwtTokenService:
    return JwtTokenService(
        secret_key=SECRETO,
        algorithm="HS256",
        access_ttl=timedelta(minutes=15),
        refresh_ttl=timedelta(days=7),
        clock=clock,
    )


def test_el_access_token_se_decodifica_con_sus_claims(service: JwtTokenService) -> None:
    # Arrange
    emitido = service.create_access_token(user_id=42)

    # Act
    claims = service.decode(emitido.value)

    # Assert
    assert claims.user_id == 42
    assert claims.token_type is TokenType.ACCESS
    assert claims.jti == emitido.jti


def test_el_refresh_token_se_marca_como_tal(service: JwtTokenService) -> None:
    # Arrange
    emitido = service.create_refresh_token(user_id=42)

    # Act
    claims = service.decode(emitido.value)

    # Assert
    assert claims.token_type is TokenType.REFRESH


def test_los_ttl_de_acceso_y_refresco_son_distintos(service: JwtTokenService) -> None:
    # Arrange / Act
    acceso = service.create_access_token(user_id=1)
    refresco = service.create_refresh_token(user_id=1)

    # Assert
    assert acceso.expires_at == AHORA + timedelta(minutes=15)
    assert refresco.expires_at == AHORA + timedelta(days=7)


def test_cada_token_tiene_un_jti_distinto(service: JwtTokenService) -> None:
    """El jti identifica la emisión: repetirlo rompería la revocación."""
    # Arrange / Act
    primero = service.create_access_token(user_id=1)
    segundo = service.create_access_token(user_id=1)

    # Assert
    assert primero.jti != segundo.jti


def test_rechaza_un_token_firmado_con_otro_secreto(service: JwtTokenService) -> None:
    # Arrange
    ajeno = jwt.encode(
        {"sub": "1", "jti": "x", "typ": "access", "iat": 0, "exp": 9999999999},
        "otro-secreto-completamente-distinto",
        algorithm="HS256",
    )

    # Act / Assert
    with pytest.raises(InvalidTokenError):
        service.decode(ajeno)


def test_rechaza_un_token_expirado(service: JwtTokenService, clock: FixedClock) -> None:
    # Arrange
    emitido = service.create_access_token(user_id=1)

    # Act
    clock.avanzar(timedelta(minutes=16))

    # Assert
    with pytest.raises(InvalidTokenError):
        service.decode(emitido.value)


@pytest.mark.parametrize("basura", ["", "no-es-un-jwt", "a.b.c", "Bearer algo"])
def test_rechaza_basura(service: JwtTokenService, basura: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(InvalidTokenError):
        service.decode(basura)


def test_rechaza_un_token_sin_los_claims_requeridos(service: JwtTokenService) -> None:
    # Arrange
    incompleto = jwt.encode({"sub": "1", "exp": 9999999999}, SECRETO, algorithm="HS256")

    # Act / Assert
    with pytest.raises(InvalidTokenError):
        service.decode(incompleto)


def test_rechaza_un_token_sin_firma(service: JwtTokenService) -> None:
    """Defensa contra el ataque clásico de cambiar `alg` a `none`.

    Se arma a mano y no con jwt.encode porque PyJWT se niega a emitirlo; la
    gracia es justamente que un atacante sí puede construirlo.
    """

    def _b64(datos: dict[str, object]) -> str:
        crudo = json.dumps(datos, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(crudo).rstrip(b"=").decode()

    # Arrange
    encabezado = _b64({"alg": "none", "typ": "JWT"})
    cuerpo = _b64({"sub": "1", "jti": "x", "typ": "access", "iat": 0, "exp": 9999999999})
    sin_firma = f"{encabezado}.{cuerpo}."

    # Act / Assert
    with pytest.raises(InvalidTokenError):
        service.decode(sin_firma)


def test_la_huella_es_determinista_y_no_contiene_el_token(service: JwtTokenService) -> None:
    # Arrange
    emitido = service.create_refresh_token(user_id=1)

    # Act
    huella = service.fingerprint(emitido.value)

    # Assert
    assert huella == service.fingerprint(emitido.value)
    assert emitido.value not in huella
    assert len(huella) == 64


def test_tokens_distintos_tienen_huellas_distintas(service: JwtTokenService) -> None:
    # Arrange
    uno = service.create_refresh_token(user_id=1)
    otro = service.create_refresh_token(user_id=2)

    # Act / Assert
    assert service.fingerprint(uno.value) != service.fingerprint(otro.value)
