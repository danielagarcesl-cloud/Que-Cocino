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
            sin_precio.append(ing_id)
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
