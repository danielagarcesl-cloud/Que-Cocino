"""Compatibilidad, cobertura, faltantes, porciones y ranking de recetas (funciones puras, sin LLM)."""
from __future__ import annotations

import math

from app.modelos import Catalogo, ItemInventario, Receta, NIVELES, RESTRICCIONES, MODOS
from app.normalizacion import convertir, resolver_ingrediente
from app.paises import nombre_local, nombre_receta

EXCLUSIONES = {
    "ninguna": set(),
    "vegetariano": {"carne", "ave", "pescado", "marisco"},
    "vegano": {"carne", "ave", "pescado", "marisco", "huevo", "lacteo", "miel"},
    "pescetariano": {"carne", "ave"},
    "sin_gluten": {"gluten"},
    "sin_lactosa": {"lacteo"},
}


# ---------- validaciones ----------
def _validar(valor, opciones, nombre):
    if valor not in opciones:
        raise ValueError(f"{nombre} inválido: {valor}. Opciones: {', '.join(opciones)}")
    return valor


def obtener_receta(receta_id: str, catalogo: Catalogo) -> Receta:
    if receta_id not in catalogo.recetas:
        raise KeyError(f"Receta desconocida: {receta_id}")
    return catalogo.recetas[receta_id]


# ---------- reglas ----------
def es_compatible(receta: Receta, restriccion: str, catalogo: Catalogo) -> bool:
    excluidas = EXCLUSIONES[_validar(restriccion, RESTRICCIONES, "restricción")]
    for item in receta.ingredientes:
        if excluidas & set(catalogo.ingredientes[item.ingrediente_id].etiquetas):
            return False
    return True


def nivel_permitido(nivel_receta: str, nivel_usuario: str) -> bool:
    _validar(nivel_usuario, NIVELES, "nivel")
    return NIVELES.index(nivel_receta) <= NIVELES.index(nivel_usuario)


# ---------- cantidades ----------
def _cantidad_base(item, catalogo: Catalogo) -> float:
    unidad_base = catalogo.ingredientes[item.ingrediente_id].unidad_base
    return convertir(item.cantidad, item.unidad, unidad_base)


def escalar_receta(receta: Receta, porciones: int, catalogo: Catalogo | None = None) -> list[dict]:
    """Multiplica por porciones / porciones_base. Devuelve cantidades en la unidad base (si hay catálogo)."""
    if porciones < 1:
        raise ValueError("Las porciones deben ser al menos 1")
    factor = porciones / receta.porciones_base
    resultado = []
    for item in receta.ingredientes:
        if catalogo:
            unidad = catalogo.ingredientes[item.ingrediente_id].unidad_base
            cantidad = _cantidad_base(item, catalogo) * factor
        else:
            unidad, cantidad = item.unidad, item.cantidad * factor
        cantidad = math.ceil(round(cantidad, 6)) if unidad == "un" else round(cantidad, 2)
        resultado.append({"ingrediente_id": item.ingrediente_id, "cantidad": cantidad, "unidad": unidad})
    return resultado


def preparar_inventario(inventario, catalogo: Catalogo) -> dict[str, float | None]:
    """Convierte la lista del usuario en {ingrediente_id: cantidad en unidad base | None (suficiente)}."""
    resultado: dict[str, float | None] = {}
    for item in inventario or []:
        if isinstance(item, str):
            item = ItemInventario(nombre=item)
        elif isinstance(item, dict):
            item = ItemInventario(**item)
        ing_id = resolver_ingrediente(item.nombre, catalogo)
        if ing_id is None:
            continue
        if item.cantidad is None:
            resultado[ing_id] = None
            continue
        unidad_base = catalogo.ingredientes[ing_id].unidad_base
        cantidad = convertir(item.cantidad, item.unidad or unidad_base, unidad_base)
        if ing_id in resultado and resultado[ing_id] is None:
            continue  # ya estaba marcado como "suficiente"
        resultado[ing_id] = (resultado.get(ing_id) or 0.0) + cantidad
    return resultado


def _no_basicos(receta: Receta, catalogo: Catalogo) -> list[str]:
    vistos = []
    for item in receta.ingredientes:
        if not catalogo.ingredientes[item.ingrediente_id].es_basico and item.ingrediente_id not in vistos:
            vistos.append(item.ingrediente_id)
    return vistos


def cobertura(receta: Receta, inventario, catalogo: Catalogo) -> float:
    inv = inventario if isinstance(inventario, dict) else preparar_inventario(inventario, catalogo)
    ids = _no_basicos(receta, catalogo)
    if not ids:
        return 1.0
    return round(sum(1 for i in ids if i in inv) / len(ids), 2)


def calcular_faltantes(receta: Receta, inventario, porciones: int, catalogo: Catalogo, pais: str | None = None) -> list[dict]:
    inv = inventario if isinstance(inventario, dict) else preparar_inventario(inventario, catalogo)
    faltantes = []
    for item in escalar_receta(receta, porciones, catalogo):
        ing_id = item["ingrediente_id"]
        if catalogo.ingredientes[ing_id].es_basico:
            continue
        necesario = item["cantidad"]
        if ing_id not in inv:
            falta = necesario
        elif inv[ing_id] is None:
            continue
        else:
            falta = round(necesario - inv[ing_id], 2)
        if falta > 0:
            faltantes.append({"ingrediente_id": ing_id, "nombre": nombre_local(ing_id, pais, catalogo),
                              "cantidad": falta, "unidad": item["unidad"]})
    return faltantes


def detalle_receta(receta_id: str, porciones: int | None, pais: str | None, catalogo: Catalogo) -> dict:
    receta = obtener_receta(receta_id, catalogo)
    porciones = porciones or receta.porciones_base
    return {
        "receta_id": receta.id,
        "nombre": nombre_receta(receta.id, pais, catalogo),
        "nivel": receta.nivel,
        "tiempo_minutos": receta.tiempo_minutos,
        "cocina_de_origen": receta.cocina_de_origen,
        "porciones": porciones,
        "ingredientes": [
            {**i, "nombre": nombre_local(i["ingrediente_id"], pais, catalogo),
             "es_basico": catalogo.ingredientes[i["ingrediente_id"]].es_basico}
            for i in escalar_receta(receta, porciones, catalogo)
        ],
        "pasos": receta.pasos,
    }


def sugerir_menu(inventario, nivel: str, restriccion: str, porciones: int, catalogo: Catalogo,
                 modo: str = "completar_comprando", pais: str | None = None, max_resultados: int = 5) -> list[dict]:
    _validar(nivel, NIVELES, "nivel")
    _validar(restriccion, RESTRICCIONES, "restricción")
    _validar(modo, MODOS, "modo")
    inv = preparar_inventario(inventario, catalogo)
    candidatas = []
    for receta in catalogo.recetas.values():
        if not es_compatible(receta, restriccion, catalogo) or not nivel_permitido(receta.nivel, nivel):
            continue
        faltantes = calcular_faltantes(receta, inv, porciones, catalogo, pais)
        if modo == "solo_lo_que_tengo" and faltantes:
            continue
        presentes = [i for i in _no_basicos(receta, catalogo) if i in inv]
        candidatas.append({
            "receta_id": receta.id,
            "nombre": nombre_receta(receta.id, pais, catalogo),
            "nivel": receta.nivel,
            "tiempo_minutos": receta.tiempo_minutos,
            "cobertura": cobertura(receta, inv, catalogo),
            "presentes": [{"ingrediente_id": i, "nombre": nombre_local(i, pais, catalogo)} for i in presentes],
            "faltantes": faltantes,
        })
    candidatas.sort(key=lambda c: (-c["cobertura"], len(c["faltantes"]), c["tiempo_minutos"]))
    return candidatas[:max(1, max_resultados)]
