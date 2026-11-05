import pytest

from app.favoritos import guardar_favorito, listar_favoritos, quitar_favorito, repetir_favorito, validar_favoritos


def test_guardar_favorita(catalogo):
    favs = guardar_favorito([], "tortilla", catalogo)
    assert len(favs) == 1
    assert favs[0]["carpeta"] == "Favoritas" and favs[0]["porciones"] == 4 and favs[0]["veces_preparada"] == 0


def test_sin_duplicados(catalogo):
    favs = guardar_favorito([], "tortilla", catalogo)
    favs = guardar_favorito(favs, "tortilla", catalogo, porciones=2)
    assert len(favs) == 1 and favs[0]["porciones"] == 2


def test_otra_carpeta(catalogo):
    favs = guardar_favorito([], "tortilla", catalogo)
    favs = guardar_favorito(favs, "tortilla", catalogo, carpeta="Cumpleaños")
    assert len(favs) == 2


def test_receta_inexistente(catalogo):
    with pytest.raises(KeyError):
        guardar_favorito([], "sushi", catalogo)


def test_limites(catalogo):
    diez_carpetas = [{"receta_id": "tortilla", "carpeta": f"C{i}"} for i in range(10)]
    with pytest.raises(ValueError):  # carpeta 11
        guardar_favorito(diez_carpetas, "budin", catalogo, carpeta="Nueva")
    cien = [{"receta_id": "tortilla", "carpeta": f"C{i % 10}"} for i in range(100)]
    with pytest.raises(ValueError):  # favorita 101
        guardar_favorito(cien, "budin", catalogo, carpeta="C0")


def test_favorita_incompatible(catalogo):
    favs = guardar_favorito(guardar_favorito([], "tortilla", catalogo), "pollo", catalogo)
    lista = listar_favoritos(favs, {"restriccion": "vegetariano"}, catalogo)
    assert len(lista) == 2
    assert {f["receta_id"]: f["compatible_con_perfil"] for f in lista} == {"tortilla": True, "pollo": False}


def test_favoritas_para_hoy(catalogo, inventario_control):
    favs = guardar_favorito([], "pollo", catalogo, ahora="2026-11-01T10:00:00+00:00")
    favs = guardar_favorito(favs, "tortilla", catalogo, ahora="2026-11-02T10:00:00+00:00")
    lista = listar_favoritos(favs, {}, catalogo, inventario=inventario_control)
    assert [(f["receta_id"], f["cobertura"]) for f in lista] == [("tortilla", 0.75), ("pollo", 0.25)]


def test_repetir_favorita_cl(catalogo, inventario_control):
    favs = guardar_favorito([], "tortilla", catalogo, porciones=2)
    r = repetir_favorito(favs, "tortilla", inventario_control, "CL", catalogo)
    assert r["faltantes"] == [{"ingrediente_id": "aceite", "nombre": "aceite", "cantidad": 25, "unidad": "ml"}]
    assert r["carrito"]["total_formateado"] == "$3.490"
    assert r["favoritos"][0]["veces_preparada"] == 1


def test_catalogo_actualizado(catalogo):
    r = validar_favoritos([{"receta_id": "tortilla"}, {"receta_id": "receta_borrada"}], catalogo)
    assert [f["receta_id"] for f in r["favoritos"]] == ["tortilla"] and r["descartados"] == ["receta_borrada"]


def test_quitar(catalogo):
    favs = guardar_favorito(guardar_favorito([], "tortilla", catalogo), "tortilla", catalogo, carpeta="Cumpleaños")
    assert len(quitar_favorito(favs, "tortilla", "Cumpleaños")) == 1
    assert quitar_favorito(favs, "tortilla") == []
