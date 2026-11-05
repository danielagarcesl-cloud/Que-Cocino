"""Nombres canónicos, sinónimos regionales y conversión de unidades (funciones puras)."""
from __future__ import annotations

import re
import unicodedata

from app.modelos import Catalogo

# consonantes tras las que un plural se forma con "es" (limón → limones, frijol → frijoles)
_PLURAL_ES = set("lrndzj")

_FACTORES = {
    "g": ("masa", 1), "kg": ("masa", 1000),
    "ml": ("volumen", 1), "l": ("volumen", 1000),
    "un": ("unidad", 1),
}


def _singular(palabra: str) -> str:
    if len(palabra) > 4 and palabra.endswith("es") and palabra[-3] in _PLURAL_ES:
        return palabra[:-2]
    if len(palabra) > 3 and palabra.endswith("s"):
        return palabra[:-1]
    return palabra


def normalizar_nombre(texto: str) -> str:
    """Minúsculas, sin tildes, sin espacios sobrantes y singular simple ("Papas " → "papa")."""
    t = unicodedata.normalize("NFD", (texto or "").strip().lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return " ".join(_singular(p) for p in t.split())


def _indice(catalogo: Catalogo) -> dict[str, str]:
    if catalogo._indice is None:
        indice: dict[str, str] = {}
        for ing in catalogo.ingredientes.values():
            nombres = [ing.id.replace("_", " "), ing.nombre, *ing.sinonimos, *ing.nombre_por_pais.values()]
            for n in nombres:
                indice.setdefault(normalizar_nombre(n), ing.id)
        catalogo._indice = indice
    return catalogo._indice


def resolver_ingrediente(texto: str, catalogo: Catalogo) -> str | None:
    """Devuelve el id canónico ("aguacate" → palta) o None si no existe en el catálogo."""
    if not texto:
        return None
    if texto in catalogo.ingredientes:
        return texto
    return _indice(catalogo).get(normalizar_nombre(texto))


def convertir(cantidad: float, desde: str, hacia: str) -> float:
    """kg↔g, l↔ml, un↔un. ValueError si las unidades son incompatibles."""
    if desde not in _FACTORES or hacia not in _FACTORES:
        raise ValueError(f"Unidad desconocida: {desde} o {hacia}")
    dim_desde, f_desde = _FACTORES[desde]
    dim_hacia, f_hacia = _FACTORES[hacia]
    if dim_desde != dim_hacia:
        raise ValueError(f"No se puede convertir {desde} a {hacia}")
    return cantidad * f_desde / f_hacia
