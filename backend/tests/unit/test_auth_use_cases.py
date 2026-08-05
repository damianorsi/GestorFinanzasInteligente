"""Tests de los casos de uso de autenticación, con repositorios en memoria."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application.dtos import TokenType
from app.application.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.application.use_cases.auth import LoginUser, LogoutUser, RefreshTokens, RegisterUser
from app.domain.default_categories import CATEGORIAS_POR_DEFECTO
from app.domain.entities import User
from app.infrastructure.security import JwtTokenService
from tests.fakes import (
    FakeCategoryRepository,
    FakePasswordHasher,
    FakeRefreshTokenRepository,
    FakeUserRepository,
    FixedClock,
)

AHORA = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
CONTRASENA = "una-contrasena-larga"


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(AHORA)


@pytest.fixture
def users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def categories() -> FakeCategoryRepository:
    return FakeCategoryRepository()


@pytest.fixture
def refresh_tokens() -> FakeRefreshTokenRepository:
    return FakeRefreshTokenRepository()


@pytest.fixture
def hasher() -> FakePasswordHasher:
    return FakePasswordHasher()


@pytest.fixture
def tokens(clock: FixedClock) -> JwtTokenService:
    return JwtTokenService(
        secret_key="secreto-de-test-con-largo-suficiente",
        algorithm="HS256",
        access_ttl=timedelta(minutes=15),
        refresh_ttl=timedelta(days=7),
        clock=clock,
    )


class TestRegisterUser:
    @pytest.fixture
    def caso(
        self,
        users: FakeUserRepository,
        categories: FakeCategoryRepository,
        hasher: FakePasswordHasher,
    ) -> RegisterUser:
        return RegisterUser(users=users, categories=categories, hasher=hasher)

    async def test_crea_el_usuario_con_la_contrasena_hasheada(
        self, caso: RegisterUser, users: FakeUserRepository, hasher: FakePasswordHasher
    ) -> None:
        # Arrange / Act
        usuario = await caso.execute(
            email="damian@ejemplo.com", password=CONTRASENA, full_name="Damián"
        )

        # Assert
        credenciales = await users.get_credentials_by_email("damian@ejemplo.com")
        assert credenciales is not None
        assert credenciales.password_hash != CONTRASENA
        assert hasher.verify(CONTRASENA, credenciales.password_hash)
        assert usuario.id is not None

    async def test_siembra_las_categorias_por_defecto(
        self, caso: RegisterUser, categories: FakeCategoryRepository
    ) -> None:
        """Una cuenta sin categorías no puede registrar un solo movimiento."""
        # Arrange / Act
        usuario = await caso.execute(
            email="damian@ejemplo.com", password=CONTRASENA, full_name="Damián"
        )

        # Assert
        assert await categories.count_for_user(usuario.id or 0) == len(CATEGORIAS_POR_DEFECTO)
        assert all(c.is_default for c in categories.categorias)
        assert all(c.user_id == usuario.id for c in categories.categorias)

    async def test_rechaza_un_email_ya_registrado(self, caso: RegisterUser) -> None:
        # Arrange
        await caso.execute(email="damian@ejemplo.com", password=CONTRASENA, full_name="Damián")

        # Act / Assert
        with pytest.raises(EmailAlreadyRegisteredError):
            await caso.execute(email="damian@ejemplo.com", password=CONTRASENA, full_name="Otro")

    async def test_el_email_se_normaliza_antes_de_comparar(self, caso: RegisterUser) -> None:
        """Sin esto, "A@B.com" y "a@b.com" serían dos cuentas distintas."""
        # Arrange
        await caso.execute(email="damian@ejemplo.com", password=CONTRASENA, full_name="Damián")

        # Act / Assert
        with pytest.raises(EmailAlreadyRegisteredError):
            await caso.execute(
                email="  DAMIAN@Ejemplo.COM  ", password=CONTRASENA, full_name="Otro"
            )


class TestLoginUser:
    @pytest.fixture
    def caso(
        self,
        users: FakeUserRepository,
        refresh_tokens: FakeRefreshTokenRepository,
        hasher: FakePasswordHasher,
        tokens: JwtTokenService,
        clock: FixedClock,
    ) -> LoginUser:
        return LoginUser(
            users=users, refresh_tokens=refresh_tokens, hasher=hasher, tokens=tokens, clock=clock
        )

    @pytest.fixture
    def usuario_registrado(self, users: FakeUserRepository, hasher: FakePasswordHasher) -> User:
        return users.agregar(
            User(email="damian@ejemplo.com", full_name="Damián"), hasher.hash(CONTRASENA)
        )

    async def test_emite_el_par_de_tokens(
        self, caso: LoginUser, usuario_registrado: User, tokens: JwtTokenService
    ) -> None:
        # Arrange / Act
        usuario, par = await caso.execute(email="damian@ejemplo.com", password=CONTRASENA)

        # Assert
        assert usuario.id == usuario_registrado.id
        assert tokens.decode(par.access.value).token_type is TokenType.ACCESS
        assert tokens.decode(par.refresh.value).token_type is TokenType.REFRESH

    async def test_guarda_la_huella_del_refresh_y_no_el_token(
        self,
        caso: LoginUser,
        usuario_registrado: User,
        refresh_tokens: FakeRefreshTokenRepository,
        tokens: JwtTokenService,
        clock: FixedClock,
    ) -> None:
        # Arrange / Act
        _, par = await caso.execute(email="damian@ejemplo.com", password=CONTRASENA)

        # Assert
        huella = tokens.fingerprint(par.refresh.value)
        assert await refresh_tokens.find_active(huella, clock.now()) is not None
        assert await refresh_tokens.find_active(par.refresh.value, clock.now()) is None

    async def test_rechaza_la_contrasena_incorrecta(
        self, caso: LoginUser, usuario_registrado: User
    ) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidCredentialsError):
            await caso.execute(email="damian@ejemplo.com", password="otra-contrasena")

    async def test_rechaza_un_email_inexistente(self, caso: LoginUser) -> None:
        # Arrange / Act / Assert
        with pytest.raises(InvalidCredentialsError):
            await caso.execute(email="nadie@ejemplo.com", password=CONTRASENA)

    async def test_con_email_inexistente_igual_gasta_tiempo_de_hashing(
        self, caso: LoginUser, hasher: FakePasswordHasher
    ) -> None:
        """Sin esto, la diferencia de tiempo permite enumerar cuentas."""
        # Arrange / Act
        with pytest.raises(InvalidCredentialsError):
            await caso.execute(email="nadie@ejemplo.com", password=CONTRASENA)

        # Assert
        assert hasher.veces_que_verifico_descartable == 1

    async def test_una_cuenta_deshabilitada_da_el_mismo_error_generico(
        self, caso: LoginUser, users: FakeUserRepository, hasher: FakePasswordHasher
    ) -> None:
        """Decir "tu cuenta está deshabilitada" confirmaría que el email existe."""
        # Arrange
        users.agregar(
            User(email="inactivo@ejemplo.com", full_name="Inactivo", is_active=False),
            hasher.hash(CONTRASENA),
        )

        # Act / Assert
        with pytest.raises(InvalidCredentialsError):
            await caso.execute(email="inactivo@ejemplo.com", password=CONTRASENA)


class TestRefreshTokens:
    @pytest.fixture
    def caso(
        self,
        users: FakeUserRepository,
        refresh_tokens: FakeRefreshTokenRepository,
        tokens: JwtTokenService,
        clock: FixedClock,
    ) -> RefreshTokens:
        return RefreshTokens(users=users, refresh_tokens=refresh_tokens, tokens=tokens, clock=clock)

    @pytest.fixture
    async def sesion_iniciada(
        self,
        users: FakeUserRepository,
        refresh_tokens: FakeRefreshTokenRepository,
        hasher: FakePasswordHasher,
        tokens: JwtTokenService,
        clock: FixedClock,
    ) -> str:
        users.agregar(User(email="damian@ejemplo.com", full_name="Damián"), hasher.hash(CONTRASENA))
        login = LoginUser(
            users=users, refresh_tokens=refresh_tokens, hasher=hasher, tokens=tokens, clock=clock
        )
        _, par = await login.execute(email="damian@ejemplo.com", password=CONTRASENA)
        return par.refresh.value

    async def test_devuelve_un_par_nuevo(
        self, caso: RefreshTokens, sesion_iniciada: str, tokens: JwtTokenService
    ) -> None:
        # Arrange / Act
        par = await caso.execute(sesion_iniciada)

        # Assert
        assert tokens.decode(par.access.value).token_type is TokenType.ACCESS
        assert par.refresh.value != sesion_iniciada

    async def test_el_refresh_usado_queda_revocado(
        self, caso: RefreshTokens, sesion_iniciada: str
    ) -> None:
        """La rotación: reusar un token ya canjeado es evidencia de robo."""
        # Arrange
        await caso.execute(sesion_iniciada)

        # Act / Assert
        with pytest.raises(InvalidTokenError):
            await caso.execute(sesion_iniciada)

    async def test_rechaza_un_access_token(
        self,
        caso: RefreshTokens,
        tokens: JwtTokenService,
        users: FakeUserRepository,
        hasher: FakePasswordHasher,
    ) -> None:
        """Sin esta comprobación, el token de 15 minutos valdría lo mismo que el de 7 días."""
        # Arrange
        usuario = users.agregar(
            User(email="damian@ejemplo.com", full_name="Damián"), hasher.hash(CONTRASENA)
        )
        acceso = tokens.create_access_token(usuario.id or 0)

        # Act / Assert
        with pytest.raises(InvalidTokenError):
            await caso.execute(acceso.value)

    async def test_rechaza_un_refresh_valido_que_nunca_se_guardo(
        self,
        caso: RefreshTokens,
        tokens: JwtTokenService,
        users: FakeUserRepository,
        hasher: FakePasswordHasher,
    ) -> None:
        """Firma correcta no alcanza: tiene que estar en el registro y vigente."""
        # Arrange
        usuario = users.agregar(
            User(email="damian@ejemplo.com", full_name="Damián"), hasher.hash(CONTRASENA)
        )
        huerfano = tokens.create_refresh_token(usuario.id or 0)

        # Act / Assert
        with pytest.raises(InvalidTokenError):
            await caso.execute(huerfano.value)

    async def test_rechaza_un_refresh_expirado(
        self, caso: RefreshTokens, sesion_iniciada: str, clock: FixedClock
    ) -> None:
        # Arrange
        clock.avanzar(timedelta(days=8))

        # Act / Assert
        with pytest.raises(InvalidTokenError):
            await caso.execute(sesion_iniciada)


class TestLogoutUser:
    @pytest.fixture
    def caso(
        self,
        refresh_tokens: FakeRefreshTokenRepository,
        tokens: JwtTokenService,
        clock: FixedClock,
    ) -> LogoutUser:
        return LogoutUser(refresh_tokens=refresh_tokens, tokens=tokens, clock=clock)

    async def test_revoca_el_refresh_token(
        self,
        caso: LogoutUser,
        users: FakeUserRepository,
        refresh_tokens: FakeRefreshTokenRepository,
        hasher: FakePasswordHasher,
        tokens: JwtTokenService,
        clock: FixedClock,
    ) -> None:
        # Arrange
        users.agregar(User(email="damian@ejemplo.com", full_name="Damián"), hasher.hash(CONTRASENA))
        login = LoginUser(
            users=users, refresh_tokens=refresh_tokens, hasher=hasher, tokens=tokens, clock=clock
        )
        _, par = await login.execute(email="damian@ejemplo.com", password=CONTRASENA)

        # Act
        await caso.execute(par.refresh.value)

        # Assert
        huella = tokens.fingerprint(par.refresh.value)
        assert await refresh_tokens.find_active(huella, clock.now()) is None

    async def test_no_falla_con_un_token_inexistente(self, caso: LogoutUser) -> None:
        """Cerrar sesión tiene que funcionar siempre desde el lado de quien lo pide."""
        # Arrange / Act / Assert
        await caso.execute("token-que-no-existe")
