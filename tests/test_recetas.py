import pytest

from app.recetas import (calcular_faltantes, cobertura, escalar_receta, es_compatible, nivel_permitido,
                         sugerir_menu)


def ids(lista, clave="ingrediente_id"):
    return [x[clave] for x in lista]


def test_cobertura_tortilla(catalogo, inventario_control):
    r = catalogo.recetas["tortilla"]
    assert cobertura(r, inventario_control, catalogo) == 0.75
    assert ids(calcular_faltantes(r, inventario_control, 4, catalogo)) == ["aceite"]


def test_cobertura_budin(catalogo, inventario_control):
    r = catalogo.recetas["budin"]
    assert cobertura(r, inventario_control, catalogo) == 0.50
    assert ids(calcular_faltantes(r, inventario_control, 4, catalogo)) == ["zapallo_italiano", "leche"]


def test_cobertura_pollo(catalogo, inventario_control):
    assert cobertura(catalogo.recetas["pollo"], inventario_control, catalogo) == 0.25


def test_filtro_vegano(catalogo, inventario_control):
    assert sugerir_menu(inventario_control, "avanzado", "vegano", 4, catalogo) == []


def test_filtro_vegetariano_avanzado(catalogo, inventario_control):
    menu = sugerir_menu(inventario_control, "avanzado", "vegetariano", 4, catalogo, modo="completar_comprando")
    assert ids(menu, "receta_id") == ["tortilla", "budin"]
    assert [m["cobertura"] for m in menu] == [0.75, 0.50]


def test_filtro_principiante_ninguna(catalogo, inventario_control):
    menu = sugerir_menu(inventario_control, "principiante", "ninguna", 4, catalogo, modo="completar_comprando")
    assert ids(menu, "receta_id") == ["tortilla", "pollo"]


def test_modo_solo_lo_que_tengo_sin_resultados(catalogo, inventario_control):
    assert sugerir_menu(inventario_control, "avanzado", "ninguna", 4, catalogo, modo="solo_lo_que_tengo") == []


def test_modo_solo_lo_que_tengo_con_aceite(catalogo, inventario_control):
    menu = sugerir_menu(inventario_control + ["aceite"], "avanzado", "ninguna", 4, catalogo, modo="solo_lo_que_tengo")
    assert ids(menu, "receta_id") == ["tortilla"]


def test_escalar_tortilla(catalogo):
    escalada = {i["ingrediente_id"]: i["cantidad"] for i in escalar_receta(catalogo.recetas["tortilla"], 2, catalogo)}
    assert escalada["papa"] == 2 and escalada["huevo"] == 2 and escalada["aceite"] == 25


def test_faltante_con_cantidad(catalogo):
    inv = [{"nombre": "papa", "cantidad": 2, "unidad": "un"}]
    faltantes = {f["ingrediente_id"]: f for f in calcular_faltantes(catalogo.recetas["tortilla"], inv, 4, catalogo)}
    assert faltantes["papa"]["cantidad"] == 2 and faltantes["papa"]["unidad"] == "un"


def test_nombres_locales_en_menu(catalogo):
    menu = sugerir_menu(["papa"], "avanzado", "ninguna", 4, catalogo, pais="ES")
    tortilla = next(m for m in menu if m["receta_id"] == "tortilla")
    assert tortilla["presentes"][0]["nombre"] == "patata"


def test_nivel_y_restriccion_invalidos(catalogo):
    with pytest.raises(ValueError):
        sugerir_menu([], "experto", "ninguna", 4, catalogo)
    with pytest.raises(ValueError):
        es_compatible(catalogo.recetas["tortilla"], "keto", catalogo)
    assert nivel_permitido("principiante", "intermedio") and not nivel_permitido("avanzado", "intermedio")
