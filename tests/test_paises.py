import pytest

from app.paises import formatear_monto, nombre_local, proveedores_de, validar_pais


def test_nombre_local(catalogo):
    assert nombre_local("palta", "MX", catalogo) == "aguacate"
    assert nombre_local("zapallo_italiano", "ES", catalogo) == "calabacín"
    assert nombre_local("palta", "CL", catalogo) == "palta"
    assert nombre_local("cebolla", "PE", catalogo) == "cebolla"  # sin entrada: usa el nombre


def test_formato_de_monto(catalogo):
    assert formatear_monto(3490, "CL", catalogo) == "$3.490"
    assert formatear_monto(89.5, "MX", catalogo) == "$89.50"
    assert formatear_monto(3.49, "ES", catalogo) == "3,49 €"


def test_pais_no_soportado(catalogo):
    with pytest.raises(ValueError):
        validar_pais("XX", catalogo)


def test_otro_solo_simulado(catalogo):
    assert proveedores_de("OTRO", catalogo) == ["simulado"]
