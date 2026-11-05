"""Catálogo mínimo de control (sección 6.7 del prompt maestro) y clientes falsos de OpenAI."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import yaml

from app.configuracion import RAIZ
from app.modelos import Catalogo, Ingrediente, Receta


def _ing(id, nombre, unidad, etiquetas=(), sinonimos=(), por_pais=None, basico=False):
    return Ingrediente(id=id, nombre=nombre, sinonimos=list(sinonimos), nombre_por_pais=por_pais or {},
                       categoria="control", unidad_base=unidad, etiquetas=list(etiquetas), es_basico=basico)


def _receta(id, nombre, nivel, tiempo, items):
    return Receta(id=id, nombre=nombre, nivel=nivel, tiempo_minutos=tiempo, porciones_base=4,
                  ingredientes=[{"ingrediente_id": a, "cantidad": b, "unidad": c} for a, b, c in items],
                  pasos=["Paso de control."])


@pytest.fixture
def catalogo() -> Catalogo:
    ingredientes = [
        _ing("sal", "sal", "g", basico=True),
        _ing("papa", "papa", "un", sinonimos=["patata"], por_pais={"ES": "patata"}),
        _ing("huevo", "huevo", "un", ["huevo"]),
        _ing("cebolla", "cebolla", "un"),
        _ing("aceite", "aceite", "ml"),
        _ing("zapallo_italiano", "zapallo italiano", "g", sinonimos=["zucchini", "calabacin"],
             por_pais={"ES": "calabacín", "MX": "calabacita"}),
        _ing("queso", "queso", "g", ["lacteo"]),
        _ing("leche", "leche", "ml", ["lacteo"]),
        _ing("pollo", "pollo", "g", ["ave"]),
        _ing("limon", "limón", "un"),
        _ing("ajo", "ajo", "un"),
        _ing("harina", "harina", "g", ["gluten"]),
        _ing("palta", "palta", "un", sinonimos=["aguacate"], por_pais={"CL": "palta", "MX": "aguacate"}),
        _ing("poroto", "poroto", "g", sinonimos=["frijol", "alubia"], por_pais={"MX": "frijol"}),
    ]
    recetas = [
        _receta("tortilla", "Tortilla de papas", "principiante", 30,
                [("papa", 4, "un"), ("huevo", 4, "un"), ("cebolla", 1, "un"), ("aceite", 50, "ml"), ("sal", 5, "g")]),
        _receta("budin", "Budín de zapallo italiano", "intermedio", 45,
                [("zapallo_italiano", 500, "g"), ("huevo", 3, "un"), ("queso", 150, "g"), ("leche", 250, "ml")]),
        _receta("pollo", "Pollo al horno con papas", "principiante", 60,
                # El prompt maestro dice "papa 1 kg", pero la papa se mide en unidades (la tortilla usa "4 un")
                # y kg → un no se puede convertir. Se usa 6 un (≈ 1 kg); la cobertura de control (0,25) no cambia.
                [("pollo", 1, "kg"), ("papa", 6, "un"), ("limon", 2, "un"), ("ajo", 3, "un"), ("sal", 8, "g")]),
    ]
    precio = lambda c, u, p: {"envase_cantidad": c, "envase_unidad": u, "precio": p, "marca_referencial": "control"}
    precios = {
        "CL": {"moneda": "CLP", "items": {"aceite": precio(1, "l", 3490), "zapallo_italiano": precio(1, "kg", 1990),
                                          "leche": precio(1, "l", 1190), "harina": precio(1, "kg", 1290)}},
        "ES": {"moneda": "EUR", "items": {"aceite": precio(1, "l", 3.49)}},
    }
    return Catalogo(
        ingredientes={i.id: i for i in ingredientes},
        recetas={r.id: r for r in recetas},
        precios=precios,
        paises=yaml.safe_load((RAIZ / "config" / "paises.yaml").read_text("utf-8")),
        proveedores=yaml.safe_load((RAIZ / "config" / "proveedores.yaml").read_text("utf-8")),
    )


INVENTARIO_CONTROL = ["papa", "huevo", "cebolla", "queso"]


@pytest.fixture
def inventario_control():
    return list(INVENTARIO_CONTROL)


# ---------- clientes falsos que imitan la forma de las respuestas de OpenAI ----------
def respuesta_falsa(contenido=None, tool_calls=None, tokens=(100, 20)):
    llamadas = None
    if tool_calls:
        llamadas = [SimpleNamespace(id=f"llamada_{i}", type="function",
                                    function=SimpleNamespace(name=n, arguments=json.dumps(a, ensure_ascii=False)))
                    for i, (n, a) in enumerate(tool_calls)]
    mensaje = SimpleNamespace(content=contenido, tool_calls=llamadas, role="assistant")
    return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)],
                           usage=SimpleNamespace(prompt_tokens=tokens[0], completion_tokens=tokens[1]))


class ClienteFalso:
    """Devuelve las respuestas en orden y guarda cada request para inspeccionarlo."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))

    def _crear(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs, default=lambda o: o.__dict__)))
        if not self.respuestas:
            raise AssertionError("El ClienteFalso no tiene más respuestas")
        return self.respuestas.pop(0)
