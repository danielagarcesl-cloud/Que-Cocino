import pytest

from app.normalizacion import convertir, normalizar_nombre, resolver_ingrediente


def test_normalizacion():
    assert normalizar_nombre(" Papas ") == "papa"


def test_normalizacion_regional(catalogo):
    assert resolver_ingrediente("Patatas", catalogo) == "papa"


def test_sinonimo(catalogo):
    assert resolver_ingrediente("zucchini", catalogo) == "zapallo_italiano"


def test_sinonimo_regional(catalogo):
    assert resolver_ingrediente("frijoles", catalogo) == "poroto"
    assert resolver_ingrediente("aguacate", catalogo) == "palta"


def test_ingrediente_desconocido(catalogo):
    assert resolver_ingrediente("cosa rara", catalogo) is None


def test_conversion():
    assert convertir(1.5, "kg", "g") == 1500


def test_unidades_incompatibles():
    with pytest.raises(ValueError):
        convertir(100, "g", "ml")
