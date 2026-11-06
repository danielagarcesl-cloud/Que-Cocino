"""Envases, cantidades a comprar y totales (funciones puras)."""
from __future__ import annotations

import math

from app.modelos import Catalogo
from app.normalizacion import convertir
from app.paises import formatear_monto, moneda_de, nombre_local

AVISO = "Precios referenciales"


def unidades_a_comprar(necesario: float, envase: float) -> int:
    """ceil(necesario / envase), con ambas cantidades en la misma unidad; mínimo 1 si necesario > 0."""
    if necesario <= 0:
        return 0
    if envase <= 0:
        raise ValueError("El envase debe ser mayor que cero")
    return max(1, math.ceil(round(necesario / envase, 6)))


def armar_carrito(faltantes: list[dict], precios_pais: dict | None, pais: str | None, catalogo: Catalogo) -> dict:
    precios = (precios_pais or {}).get("items", {})
    items, sin_precio, total = [], [], 0.0
    for f in faltantes:
        ing_id = f["ingrediente_id"]
        precio = precios.get(ing_id)
        if not precio:
            # Igual va al carrito: el usuario lo necesita aunque no tengamos precio de referencia.
            sin_precio.append(ing_id)
            items.append({
                "ingrediente_id": ing_id,
                "nombre": nombre_local(ing_id, pais, catalogo),
                "necesario": f["cantidad"],
                "unidad": f["unidad"],
                "con_precio": False,
                "envase": None,
                "unidades": None,
                "precio_unitario": None,
                "precio_unitario_formateado": None,
                "subtotal": None,
                "subtotal_formateado": None,
            })
            continue
        envase = convertir(precio["envase_cantidad"], precio["envase_unidad"], f["unidad"])
        unidades = unidades_a_comprar(f["cantidad"], envase)
        subtotal = round(unidades * precio["precio"], 2)
        total += subtotal
        items.append({
            "ingrediente_id": ing_id,
            "nombre": nombre_local(ing_id, pais, catalogo),
            "necesario": f["cantidad"],
            "unidad": f["unidad"],
            "con_precio": True,
            "envase": f'{precio["envase_cantidad"]} {precio["envase_unidad"]}',
            "unidades": unidades,
            "precio_unitario": precio["precio"],
            "precio_unitario_formateado": formatear_monto(precio["precio"], pais, catalogo),
            "subtotal": subtotal,
            "subtotal_formateado": formatear_monto(subtotal, pais, catalogo),
        })
    total = round(total, 2)
    return {
        "items": items,
        "total": total,
        "moneda": (precios_pais or {}).get("moneda") or moneda_de(pais, catalogo),
        "total_formateado": formatear_monto(total, pais, catalogo),
        "sin_precio": sin_precio,
        "aviso": AVISO,
    }


# ---------------------------------------------------------------- "Mi carrito" editable
MAX_PRODUCTOS = 60
MAX_LARGO_NOMBRE = 60
MAX_UNIDADES = 99


def _clave(ingrediente_id: str, nombre: str) -> str:
    return f"{ingrediente_id}|{' '.join(nombre.lower().split())}"


def recalcular_carrito(entradas: list[dict], precios_pais: dict | None, pais: str | None, catalogo: Catalogo) -> dict:
    """Recalcula "Mi carrito" después de que el usuario lo edita.

    Cada entrada trae ingrediente_id, cantidad necesaria y, si el usuario los cambió, un nombre propio
    (por ejemplo "leche semidescremada") y las unidades a comprar. Los productos iguales se juntan.
    El precio referencial siempre es el del ingrediente del catálogo: si el usuario elige una variante,
    se avisa que el precio es del ingrediente original.
    """
    if len(entradas) > MAX_PRODUCTOS:
        raise ValueError(f"El carrito admite hasta {MAX_PRODUCTOS} productos.")
    precios = (precios_pais or {}).get("items", {})

    # 1. juntar productos repetidos (mismo ingrediente y mismo nombre)
    juntos: dict[str, dict] = {}
    for e in entradas:
        ing_id = e["ingrediente_id"]
        if ing_id not in catalogo.ingredientes:
            raise ValueError(f"Ingrediente desconocido: {ing_id}")
        original = nombre_local(ing_id, pais, catalogo)
        nombre = " ".join(str(e.get("nombre") or "").split())[:MAX_LARGO_NOMBRE] or original
        clave = _clave(ing_id, nombre)
        manual = e.get("unidades")
        if manual is not None and not 1 <= int(manual) <= MAX_UNIDADES:
            raise ValueError(f"Las unidades deben estar entre 1 y {MAX_UNIDADES}.")
        if clave not in juntos:
            juntos[clave] = {"ingrediente_id": ing_id, "nombre": nombre, "nombre_original": original,
                             "necesario": 0.0, "unidad": e["unidad"], "manuales": [], "recetas": []}
        item = juntos[clave]
        item["necesario"] = round(item["necesario"] + convertir(float(e["necesario"]), e["unidad"], item["unidad"]), 2)
        item["manuales"].append(int(manual) if manual is not None else None)
        for r in e.get("recetas") or []:
            if r not in item["recetas"]:
                item["recetas"].append(r)

    # 2. precios y totales (siempre con los precios referenciales del país)
    items, sin_precio, total = [], [], 0.0
    for clave, j in juntos.items():
        precio = precios.get(j["ingrediente_id"])
        envase = convertir(precio["envase_cantidad"], precio["envase_unidad"], j["unidad"]) if precio else None
        calculadas = unidades_a_comprar(j["necesario"], envase) if precio else None
        manuales = [m for m in j["manuales"] if m is not None]
        hay_manual = bool(manuales)
        if not hay_manual:
            unidades = calculadas  # None si no hay precio: no sabemos el tamaño del envase
        elif len(manuales) == len(j["manuales"]) or calculadas is None:
            unidades = sum(manuales)
        else:
            # se juntó un producto editado a mano con uno nuevo: nunca menos de lo que la receta necesita
            unidades = max(sum(manuales), calculadas)
        subtotal = round(unidades * precio["precio"], 2) if precio else None
        if precio:
            total += subtotal
        else:
            sin_precio.append(j["ingrediente_id"])
        items.append({
            "clave": clave,
            "ingrediente_id": j["ingrediente_id"],
            "nombre": j["nombre"],
            "nombre_original": j["nombre_original"],
            "personalizado": j["nombre"].lower() != j["nombre_original"].lower(),
            "necesario": j["necesario"],
            "unidad": j["unidad"],
            "con_precio": bool(precio),
            "envase": f'{precio["envase_cantidad"]} {precio["envase_unidad"]}' if precio else None,
            "unidades": unidades,
            "unidades_manual": hay_manual,
            "precio_unitario_formateado": formatear_monto(precio["precio"], pais, catalogo) if precio else None,
            "subtotal": subtotal,
            "subtotal_formateado": formatear_monto(subtotal, pais, catalogo) if precio else None,
            "recetas": j["recetas"],
        })
    total = round(total, 2)
    return {
        "items": items,
        "total": total,
        "moneda": (precios_pais or {}).get("moneda") or moneda_de(pais, catalogo),
        "total_formateado": formatear_monto(total, pais, catalogo),
        "sin_precio": sin_precio,
        "aviso": AVISO,
    }
