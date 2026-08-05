"""Tests de los casos de uso del ABM de categorías."""

from __future__ import annotations

import pytest

from app.application.dtos import CategoryUsage
from app.application.exceptions import (
    DuplicateResourceError,
    ResourceInUseError,
    ResourceNotFoundError,
)
from app.application.use_cases.categories import (
    CreateCategory,
    DeleteCategory,
    GetCategory,
    ListCategories,
    UpdateCategory,
)
from app.domain.entities import Category
from app.domain.enums import TransactionType
from app.domain.exceptions import InvalidCategoryError
from tests.fakes import FakeCategoryRepository

USUARIO = 1
OTRO_USUARIO = 2


@pytest.fixture
def repo() -> FakeCategoryRepository:
    return FakeCategoryRepository()


async def _sembrar(
    repo: FakeCategoryRepository,
    user_id: int,
    nombre: str,
    tipo: TransactionType = TransactionType.EXPENSE,
) -> Category:
    categoria = Category(user_id=user_id, name=nombre, type=tipo)
    return await repo.create(categoria)


class TestCreateCategory:
    async def test_crea_la_categoria(self, repo: FakeCategoryRepository) -> None:
        # Arrange
        caso = CreateCategory(repo)

        # Act
        creada = await caso.execute(
            user_id=USUARIO, name="  Mascotas  ", type=TransactionType.EXPENSE, color="#AABBCC"
        )

        # Assert
        assert creada.id is not None
        assert creada.name == "Mascotas"
        assert creada.color == "#aabbcc"

    async def test_rechaza_un_nombre_duplicado_del_mismo_tipo(
        self, repo: FakeCategoryRepository
    ) -> None:
        # Arrange
        await _sembrar(repo, USUARIO, "Ocio")
        caso = CreateCategory(repo)

        # Act / Assert
        with pytest.raises(DuplicateResourceError, match="Ocio"):
            await caso.execute(user_id=USUARIO, name="Ocio", type=TransactionType.EXPENSE)

    async def test_permite_el_mismo_nombre_en_otro_tipo(self, repo: FakeCategoryRepository) -> None:
        """ "Otros" puede existir como ingreso y como gasto a la vez."""
        # Arrange
        await _sembrar(repo, USUARIO, "Otros", TransactionType.EXPENSE)
        caso = CreateCategory(repo)

        # Act
        creada = await caso.execute(user_id=USUARIO, name="Otros", type=TransactionType.INCOME)

        # Assert
        assert creada.type is TransactionType.INCOME

    async def test_el_duplicado_se_evalua_por_usuario(self, repo: FakeCategoryRepository) -> None:
        """Que otra persona tenga "Ocio" no puede impedirme crear la mía."""
        # Arrange
        await _sembrar(repo, OTRO_USUARIO, "Ocio")
        caso = CreateCategory(repo)

        # Act
        creada = await caso.execute(user_id=USUARIO, name="Ocio", type=TransactionType.EXPENSE)

        # Assert
        assert creada.user_id == USUARIO

    async def test_el_nombre_se_recorta_antes_de_comparar(
        self, repo: FakeCategoryRepository
    ) -> None:
        """Sin esto, "Ocio" y " Ocio " convivirían como categorías distintas."""
        # Arrange
        await _sembrar(repo, USUARIO, "Ocio")
        caso = CreateCategory(repo)

        # Act / Assert
        with pytest.raises(DuplicateResourceError):
            await caso.execute(user_id=USUARIO, name="  Ocio  ", type=TransactionType.EXPENSE)


class TestListCategories:
    async def test_solo_devuelve_las_propias(self, repo: FakeCategoryRepository) -> None:
        # Arrange
        await _sembrar(repo, USUARIO, "Mía")
        await _sembrar(repo, OTRO_USUARIO, "Ajena")
        caso = ListCategories(repo)

        # Act
        resultado = await caso.execute(user_id=USUARIO)

        # Assert
        assert [c.name for c in resultado] == ["Mía"]

    async def test_filtra_por_tipo(self, repo: FakeCategoryRepository) -> None:
        # Arrange
        await _sembrar(repo, USUARIO, "Sueldo", TransactionType.INCOME)
        await _sembrar(repo, USUARIO, "Ocio", TransactionType.EXPENSE)
        caso = ListCategories(repo)

        # Act
        ingresos = await caso.execute(user_id=USUARIO, type=TransactionType.INCOME)

        # Assert
        assert [c.name for c in ingresos] == ["Sueldo"]

    async def test_el_orden_es_estable(self, repo: FakeCategoryRepository) -> None:
        """El selector del frontend no puede cambiar de orden entre requests."""
        # Arrange
        await _sembrar(repo, USUARIO, "Zapatos")
        await _sembrar(repo, USUARIO, "Alimentación")
        caso = ListCategories(repo)

        # Act
        resultado = await caso.execute(user_id=USUARIO)

        # Assert
        assert [c.name for c in resultado] == ["Alimentación", "Zapatos"]


class TestGetCategory:
    async def test_devuelve_la_propia(self, repo: FakeCategoryRepository) -> None:
        # Arrange
        creada = await _sembrar(repo, USUARIO, "Ocio")
        caso = GetCategory(repo)

        # Act / Assert
        assert (await caso.execute(USUARIO, creada.id or 0)).name == "Ocio"

    async def test_una_categoria_ajena_es_un_404(self, repo: FakeCategoryRepository) -> None:
        """404 y no 403: un 403 confirmaría que ese id existe."""
        # Arrange
        ajena = await _sembrar(repo, OTRO_USUARIO, "Ajena")
        caso = GetCategory(repo)

        # Act / Assert
        with pytest.raises(ResourceNotFoundError):
            await caso.execute(USUARIO, ajena.id or 0)


class TestUpdateCategory:
    async def test_cambia_el_nombre(self, repo: FakeCategoryRepository) -> None:
        # Arrange
        creada = await _sembrar(repo, USUARIO, "Ocio")
        caso = UpdateCategory(repo)

        # Act
        actualizada = await caso.execute(USUARIO, creada.id or 0, name="Entretenimiento")

        # Assert
        assert actualizada.name == "Entretenimiento"

    async def test_renombrar_sin_cambiar_nada_no_choca_consigo_misma(
        self, repo: FakeCategoryRepository
    ) -> None:
        """Por esto `exists_with_name` acepta `exclude_id`."""
        # Arrange
        creada = await _sembrar(repo, USUARIO, "Ocio")
        caso = UpdateCategory(repo)

        # Act
        actualizada = await caso.execute(USUARIO, creada.id or 0, name="Ocio", color="#112233")

        # Assert
        assert actualizada.color == "#112233"

    async def test_rechaza_un_nombre_ya_usado_por_otra(self, repo: FakeCategoryRepository) -> None:
        # Arrange
        await _sembrar(repo, USUARIO, "Ocio")
        otra = await _sembrar(repo, USUARIO, "Salud")
        caso = UpdateCategory(repo)

        # Act / Assert
        with pytest.raises(DuplicateResourceError):
            await caso.execute(USUARIO, otra.id or 0, name="Ocio")

    async def test_no_se_puede_editar_una_ajena(self, repo: FakeCategoryRepository) -> None:
        # Arrange
        ajena = await _sembrar(repo, OTRO_USUARIO, "Ajena")
        caso = UpdateCategory(repo)

        # Act / Assert
        with pytest.raises(ResourceNotFoundError):
            await caso.execute(USUARIO, ajena.id or 0, name="Robada")

    async def test_un_color_invalido_es_rechazado_por_la_entidad(
        self, repo: FakeCategoryRepository
    ) -> None:
        # Arrange
        creada = await _sembrar(repo, USUARIO, "Ocio")
        caso = UpdateCategory(repo)

        # Act / Assert
        with pytest.raises(InvalidCategoryError):
            await caso.execute(USUARIO, creada.id or 0, color="rojo")


class TestDeleteCategory:
    async def test_borra_una_categoria_sin_uso(self, repo: FakeCategoryRepository) -> None:
        # Arrange
        creada = await _sembrar(repo, USUARIO, "Ocio")
        caso = DeleteCategory(repo)

        # Act
        await caso.execute(USUARIO, creada.id or 0)

        # Assert
        assert await repo.get_for_user(USUARIO, creada.id or 0) is None

    async def test_no_se_puede_borrar_una_ajena(self, repo: FakeCategoryRepository) -> None:
        # Arrange
        ajena = await _sembrar(repo, OTRO_USUARIO, "Ajena")
        caso = DeleteCategory(repo)

        # Act / Assert
        with pytest.raises(ResourceNotFoundError):
            await caso.execute(USUARIO, ajena.id or 0)
        assert await repo.get_for_user(OTRO_USUARIO, ajena.id or 0) is not None

    async def test_el_mensaje_enumera_lo_que_bloquea_el_borrado(
        self, repo: FakeCategoryRepository
    ) -> None:
        """Un 409 que solo diga "está en uso" obliga a adivinar qué borrar."""
        # Arrange
        creada = await _sembrar(repo, USUARIO, "Alimentación")
        repo.usos[creada.id or 0] = CategoryUsage(transactions=12, budgets=1, recurring_rules=2)
        caso = DeleteCategory(repo)

        # Act / Assert
        with pytest.raises(ResourceInUseError) as error:
            await caso.execute(USUARIO, creada.id or 0)
        mensaje = str(error.value)
        assert "Alimentación" in mensaje
        assert "12 movimientos" in mensaje
        assert "1 presupuesto" in mensaje
        assert "2 reglas recurrentes" in mensaje

    @pytest.mark.parametrize(
        ("uso", "esperado"),
        [
            (CategoryUsage(1, 0, 0), "1 movimiento"),
            (CategoryUsage(0, 3, 0), "3 presupuestos"),
            (CategoryUsage(0, 0, 1), "1 regla recurrente"),
            (CategoryUsage(2, 1, 0), "2 movimientos y 1 presupuesto"),
        ],
    )
    async def test_la_enumeracion_concuerda_en_numero(
        self, repo: FakeCategoryRepository, uso: CategoryUsage, esperado: str
    ) -> None:
        # Arrange
        creada = await _sembrar(repo, USUARIO, "Ocio")
        repo.usos[creada.id or 0] = uso
        caso = DeleteCategory(repo)

        # Act / Assert
        with pytest.raises(ResourceInUseError) as error:
            await caso.execute(USUARIO, creada.id or 0)
        assert esperado in str(error.value)
