"""Integridad del catálogo real (data/)."""
from collections import Counter

from app.modelos import cargar_catalogo
from app.normalizacion import normalizar_nombre
from app.recetas import es_compatible

cat = cargar_catalogo()
ANIMALES = {"huevo", "lacteo", "miel", "carne", "ave", "pescado", "marisco"}


def test_veganas_sin_ingredientes_animales():
    for r in cat.recetas.values():
        if es_compatible(r, "vegano", cat):
            etiquetas = {e for i in r.ingredientes for e in cat.ingredientes[i.ingrediente_id].etiquetas}
            assert not etiquetas & ANIMALES, r.id


def test_ingredientes_existen():
    for r in cat.recetas.values():
        for i in r.ingredientes:
            assert i.ingrediente_id in cat.ingredientes, (r.id, i.ingrediente_id)


def test_minimos_del_catalogo():
    recetas = list(cat.recetas.values())
    assert len(recetas) >= 30
    origenes = Counter(r.cocina_de_origen for r in recetas if r.cocina_de_origen != "varios")
    assert len(origenes) >= 6
    assert max(origenes.values()) <= len(recetas) / 3
    assert sum(es_compatible(r, "vegano", cat) for r in recetas) >= 5
    assert sum(es_compatible(r, "sin_gluten", cat) for r in recetas) >= 5
    assert sum(r.nivel == "principiante" for r in recetas) >= 5


def test_sinonimos_unicos():
    vistos = {}
    for ing in cat.ingredientes.values():
        for n in {normalizar_nombre(x) for x in [ing.nombre, *ing.sinonimos, *ing.nombre_por_pais.values()]}:
            assert vistos.setdefault(n, ing.id) == ing.id, f"'{n}' apunta a {vistos[n]} y a {ing.id}"


def test_unidades_convertibles():
    from app.normalizacion import convertir
    for r in cat.recetas.values():
        for i in r.ingredientes:
            convertir(i.cantidad, i.unidad, cat.ingredientes[i.ingrediente_id].unidad_base)


def test_precios_obligatorios():
    for pais in ("CL", "MX", "ES"):
        assert pais in cat.precios
        for ing_id in cat.precios[pais]["items"]:
            assert ing_id in cat.ingredientes
