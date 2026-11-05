from app.carrito import armar_carrito, unidades_a_comprar
from app.recetas import calcular_faltantes


def test_carrito_tortilla_cl(catalogo):
    c = armar_carrito([{"ingrediente_id": "aceite", "cantidad": 50, "unidad": "ml"}], catalogo.precios["CL"], "CL", catalogo)
    assert c["items"][0]["unidades"] == 1
    assert c["total"] == 3490 and c["total_formateado"] == "$3.490"
    assert c["aviso"] == "Precios referenciales"


def test_carrito_tortilla_es(catalogo):
    c = armar_carrito([{"ingrediente_id": "aceite", "cantidad": 50, "unidad": "ml"}], catalogo.precios["ES"], "ES", catalogo)
    assert c["items"][0]["unidades"] == 1 and c["total_formateado"] == "3,49 €"


def test_carrito_budin_cl(catalogo, inventario_control):
    faltantes = calcular_faltantes(catalogo.recetas["budin"], inventario_control, 4, catalogo)
    c = armar_carrito(faltantes, catalogo.precios["CL"], "CL", catalogo)
    assert c["total"] == 3180


def test_redondeo_de_envases(catalogo):
    assert unidades_a_comprar(1500, 1000) == 2
    c = armar_carrito([{"ingrediente_id": "harina", "cantidad": 1500, "unidad": "g"}], catalogo.precios["CL"], "CL", catalogo)
    assert c["items"][0]["unidades"] == 2 and c["total"] == 2580


def test_pais_sin_precios(catalogo):
    c = armar_carrito([{"ingrediente_id": "aceite", "cantidad": 50, "unidad": "ml"}], catalogo.precios.get("PE"), "PE", catalogo)
    assert c["total"] == 0 and c["sin_precio"] == ["aceite"]


def test_minimo_una_unidad():
    assert unidades_a_comprar(1, 1000) == 1 and unidades_a_comprar(0, 1000) == 0
