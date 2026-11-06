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


def test_carrito_incluye_todo_aunque_no_tenga_precio(catalogo):
    """Todo lo que falta va al carrito; lo que no tiene precio queda marcado y no suma al total."""
    faltantes = [{"ingrediente_id": "aceite", "cantidad": 50, "unidad": "ml"},
                 {"ingrediente_id": "huevo", "cantidad": 2, "unidad": "un"}]
    c = armar_carrito(faltantes, {"moneda": "ARS", "items": {}}, "AR", catalogo)
    assert [i["ingrediente_id"] for i in c["items"]] == ["aceite", "huevo"]
    assert all(i["con_precio"] is False and i["subtotal"] is None for i in c["items"])
    assert c["total"] == 0 and c["sin_precio"] == ["aceite", "huevo"]


def test_cada_producto_trae_su_enlace_de_la_tienda(catalogo):
    from app.proveedores import cotizar_compra
    faltantes = [{"ingrediente_id": "aceite", "cantidad": 50, "unidad": "ml"}]
    c = cotizar_compra(faltantes, "CL", "jumbo", catalogo)
    assert c["items"][0]["con_precio"] is True
    assert c["items"][0]["url"].startswith("https://www.jumbo.cl/busqueda?ft=")
    sin_tienda = cotizar_compra(faltantes, "CL", "simulado", catalogo)
    assert sin_tienda["items"][0]["url"] is None


# ---------------------------------------------------------------- "Mi carrito" editable
def test_mi_carrito_junta_productos_de_varias_recetas(catalogo):
    from app.carrito import recalcular_carrito
    entradas = [{"ingrediente_id": "leche", "necesario": 250, "unidad": "ml", "recetas": ["Budín"]},
                {"ingrediente_id": "leche", "necesario": 0.9, "unidad": "l", "recetas": ["Panqueques"]}]
    c = recalcular_carrito(entradas, catalogo.precios["CL"], "CL", catalogo)
    assert len(c["items"]) == 1
    leche = c["items"][0]
    assert leche["necesario"] == 1150 and leche["unidades"] == 2 and leche["subtotal"] == 2380
    assert leche["recetas"] == ["Budín", "Panqueques"] and c["total_formateado"] == "$2.380"


def test_mi_carrito_variante_y_unidades_a_mano(catalogo):
    from app.carrito import recalcular_carrito
    entradas = [{"ingrediente_id": "leche", "necesario": 250, "unidad": "ml", "nombre": "leche semidescremada", "unidades": 3}]
    c = recalcular_carrito(entradas, catalogo.precios["CL"], "CL", catalogo)
    item = c["items"][0]
    assert item["nombre"] == "leche semidescremada" and item["personalizado"] is True
    assert item["unidades"] == 3 and item["subtotal"] == 3570  # precio referencial de la leche original


def test_mi_carrito_valida_datos(catalogo):
    import pytest
    from app.carrito import recalcular_carrito
    with pytest.raises(ValueError):
        recalcular_carrito([{"ingrediente_id": "sushi", "necesario": 1, "unidad": "un"}], None, "CL", catalogo)
    with pytest.raises(ValueError):
        recalcular_carrito([{"ingrediente_id": "leche", "necesario": 1, "unidad": "l", "unidades": 500}], None, "CL", catalogo)


def test_mi_carrito_enlace_busca_la_variante(catalogo):
    from app.proveedores import cotizar_carrito_editable
    c = cotizar_carrito_editable([{"ingrediente_id": "leche", "necesario": 1, "unidad": "l", "nombre": "leche semidescremada"}],
                                 "CL", "jumbo", catalogo)
    assert c["items"][0]["url"] == "https://www.jumbo.cl/busqueda?ft=leche%20semidescremada"
    assert "aviso_variantes" in c
