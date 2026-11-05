import pytest

from app.proveedores import cotizar_compra, obtener_proveedor
from app.proveedores.enlaces import ProveedorEnlace


def test_url_codificada(catalogo):
    p = ProveedorEnlace("prueba", {"nombre": "Prueba", "plantillas": {"ES": "https://ejemplo.test/buscar?q={consulta}"}}, catalogo)
    assert p.url_busqueda("zapallo italiano", "ES").endswith("zapallo%20italiano")
    enlaces = p.enlace_compra([{"ingrediente_id": "zapallo_italiano", "cantidad": 500, "unidad": "g"}], "ES")
    assert enlaces[0]["url"].endswith("calabac%C3%ADn")


def test_proveedor_no_disponible_en_pais(catalogo):
    with pytest.raises(ValueError):
        obtener_proveedor("jumbo", "MX", catalogo)


def test_cotizar_con_enlaces_informa_tipo(catalogo):
    c = cotizar_compra([{"ingrediente_id": "aceite", "cantidad": 50, "unidad": "ml"}], "CL", "rappi", catalogo)
    assert c["tipo_integracion"] == "enlace_busqueda" and c["total_formateado"] == "$3.490"
    assert c["enlaces"][0]["url"].startswith("https://")


def test_simulado_por_defecto(catalogo):
    c = cotizar_compra([{"ingrediente_id": "aceite", "cantidad": 50, "unidad": "ml"}], "CL", None, catalogo)
    assert c["proveedor"] == "simulado" and c["enlaces"] == []
