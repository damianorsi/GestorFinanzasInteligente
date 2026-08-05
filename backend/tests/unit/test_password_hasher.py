"""Tests del hashing de contraseñas con Argon2id."""

from __future__ import annotations

import pytest

from app.infrastructure.security import Argon2Hasher


@pytest.fixture(scope="module")
def hasher() -> Argon2Hasher:
    """De alcance módulo: construirlo calcula el hash descartable, que es caro."""
    return Argon2Hasher()


def test_el_hash_no_contiene_la_contrasena(hasher: Argon2Hasher) -> None:
    # Arrange
    contrasena = "una-contrasena-larga-y-secreta"

    # Act
    resultado = hasher.hash(contrasena)

    # Assert
    assert contrasena not in resultado
    assert resultado.startswith("$argon2id$")


def test_verifica_la_contrasena_correcta(hasher: Argon2Hasher) -> None:
    # Arrange
    contrasena = "una-contrasena-larga"
    almacenado = hasher.hash(contrasena)

    # Act / Assert
    assert hasher.verify(contrasena, almacenado)


def test_rechaza_la_contrasena_incorrecta(hasher: Argon2Hasher) -> None:
    # Arrange
    almacenado = hasher.hash("la-correcta")

    # Act / Assert
    assert not hasher.verify("la-incorrecta", almacenado)


def test_dos_hashes_de_la_misma_contrasena_son_distintos(hasher: Argon2Hasher) -> None:
    """Cada hash lleva su propia sal: dos iguales delatarían que no la usa."""
    # Arrange
    contrasena = "misma-contrasena"

    # Act
    primero, segundo = hasher.hash(contrasena), hasher.hash(contrasena)

    # Assert
    assert primero != segundo
    assert hasher.verify(contrasena, primero)
    assert hasher.verify(contrasena, segundo)


def test_un_hash_corrupto_no_explota_devuelve_falso(hasher: Argon2Hasher) -> None:
    # Arrange / Act / Assert
    assert not hasher.verify("cualquier-cosa", "esto-no-es-un-hash")


def test_no_trunca_contrasenas_largas(hasher: Argon2Hasher) -> None:
    """El motivo de elegir Argon2 sobre bcrypt, que trunca a 72 bytes.

    Con bcrypt estas dos contraseñas —idénticas en sus primeros 72 bytes—
    validarían una contra el hash de la otra.
    """
    # Arrange
    base = "x" * 72
    almacenado = hasher.hash(base + "final-A")

    # Act / Assert
    assert not hasher.verify(base + "final-B", almacenado)
    assert hasher.verify(base + "final-A", almacenado)


def test_verify_dummy_no_lanza(hasher: Argon2Hasher) -> None:
    """Existe para igualar tiempos; nunca tiene que fallar."""
    # Arrange / Act / Assert
    hasher.verify_dummy("cualquier-cosa")
