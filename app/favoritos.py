"""Carpetas de recetas favoritas: guardar, quitar, listar y repetir (funciones puras, sin LLM).

Las favoritas viven en el navegador del usuario. El servidor recibe la lista, la modifica aquí
y la devuelve: nunca la guarda. El LLM tampoco la edita; solo llama estas funciones.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.carrito import armar_carrito
from app.modelos import Catalogo, Favorito, Perfil
from app.paises import nombre_receta
from app.recetas import (calcular_faltantes, cobertura, detalle_receta, es_compatible,
                         nivel_permitido, obtener_receta, preparar_inventario)

MAX_FAVORITOS = 100
MAX_CARPETAS = 10
CARPETA_POR_DEFECTO = "Favoritas"


def _ahora() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _cargar(favoritos) -> list[Favorito]:
    return [f if isinstance(f, Favorito) else Favorito(**f) for f in (favoritos or [])]


def _volcar(favoritos: list[Favorito]) -> list[dict]:
    return [f.model_dump() for f in favoritos]


def guardar_favorito(favoritos, receta_id: str, catalogo: Catalogo, carpeta: str | None = None,
                     porciones: int | None = None, nota: str = "", ahora: str | None = None) -> list[dict]:
    receta = obtener_receta(receta_id, catalogo)  # KeyError si no existe
    carpeta = (carpeta or CARPETA_POR_DEFECTO).strip() or CARPETA_POR_DEFECTO
    lista = _cargar(favoritos)
    for f in lista:
        if f.receta_id == receta_id and f.carpeta == carpeta:  # ya existe: actualiza sin duplicar
            if porciones:
                f.porciones = porciones
            if nota:
                f.nota = nota
            return _volcar(lista)
    if len(lista) >= MAX_FAVORITOS:
        raise ValueError(f"Llegaste al máximo de {MAX_FAVORITOS} favoritas. Quita alguna para guardar otra.")
    carpetas = {f.carpeta for f in lista}
    if carpeta not in carpetas and len(carpetas) >= MAX_CARPETAS:
        raise ValueError(f"Llegaste al máximo de {MAX_CARPETAS} carpetas. Usa una existente.")
    lista.append(Favorito(receta_id=receta_id, carpeta=carpeta, porciones=porciones or receta.porciones_base,
                          nota=nota or "", guardado_en=ahora or _ahora()))
    return _volcar(lista)


def quitar_favorito(favoritos, receta_id: str, carpeta: str | None = None) -> list[dict]:
    lista = _cargar(favoritos)
    restantes = [f for f in lista if not (f.receta_id == receta_id and (carpeta is None or f.carpeta == carpeta))]
    if len(restantes) == len(lista):
        raise KeyError(f"La receta {receta_id} no está en tus favoritas")
    return _volcar(restantes)


def validar_favoritos(favoritos, catalogo: Catalogo) -> dict:
    """Quita las favoritas cuya receta ya no existe en el catálogo y las informa."""
    validas, descartados = [], []
    for f in favoritos or []:
        try:
            fav = f if isinstance(f, Favorito) else Favorito(**f)
        except Exception:
            descartados.append(f.get("receta_id", "?") if isinstance(f, dict) else str(f))
            continue
        (validas if fav.receta_id in catalogo.recetas else descartados).append(
            fav if fav.receta_id in catalogo.recetas else fav.receta_id)
    return {"favoritos": _volcar(validas), "descartados": descartados}


def _compatible(receta, perfil: Perfil, catalogo: Catalogo) -> bool:
    return (es_compatible(receta, perfil.restriccion or "ninguna", catalogo)
            and nivel_permitido(receta.nivel, perfil.nivel or "avanzado"))


def listar_favoritos(favoritos, perfil: Perfil | dict | None, catalogo: Catalogo,
                     carpeta: str | None = None, inventario=None) -> list[dict]:
    perfil = perfil if isinstance(perfil, Perfil) else Perfil(**(perfil or {}))
    lista = validar_favoritos(favoritos, catalogo)["favoritos"]
    inv = preparar_inventario(inventario, catalogo) if inventario is not None else None
    resultado = []
    for f in lista:
        if carpeta and f["carpeta"] != carpeta:
            continue
        receta = catalogo.recetas[f["receta_id"]]
        resultado.append({
            **f,
            "nombre": nombre_receta(receta.id, perfil.pais, catalogo),
            "nivel": receta.nivel,
            "tiempo_minutos": receta.tiempo_minutos,
            "compatible_con_perfil": _compatible(receta, perfil, catalogo),
            "cobertura": cobertura(receta, inv, catalogo) if inv is not None else None,
        })
    resultado.sort(key=lambda x: x["guardado_en"], reverse=True)
    if inv is not None:
        resultado.sort(key=lambda x: -x["cobertura"])  # orden estable: a igual cobertura, la más reciente
    return resultado


def repetir_favorito(favoritos, receta_id: str, inventario, pais: str | None, catalogo: Catalogo,
                     porciones: int | None = None, carpeta: str | None = None) -> dict:
    lista = _cargar(favoritos)
    fav = next((f for f in lista if f.receta_id == receta_id and (carpeta is None or f.carpeta == carpeta)), None)
    if fav is None:
        raise KeyError(f"La receta {receta_id} no está en tus favoritas")
    receta = obtener_receta(receta_id, catalogo)
    porciones = porciones or fav.porciones or receta.porciones_base
    faltantes = calcular_faltantes(receta, inventario, porciones, catalogo, pais)
    pais_precios = (pais or "").upper()
    carrito = armar_carrito(faltantes, catalogo.precios.get(pais_precios), pais, catalogo)
    fav.veces_preparada += 1
    return {
        "detalle": detalle_receta(receta_id, porciones, pais, catalogo),
        "faltantes": faltantes,
        "carrito": carrito,
        "favoritos": _volcar(lista),
    }
