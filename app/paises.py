"""Vocabulario local, moneda y formato de montos por país (todo sale de config/paises.yaml)."""
from __future__ import annotations

from app.modelos import Catalogo


def validar_pais(pais: str | None, catalogo: Catalogo) -> str:
    """Devuelve el código en mayúsculas o lanza ValueError si el país no está soportado."""
    codigo = (pais or "OTRO").upper()
    if codigo not in catalogo.paises:
        raise ValueError(f"País no soportado: {pais}. Opciones: {', '.join(catalogo.paises)}")
    return codigo


def nombre_local(ingrediente_id: str, pais: str | None, catalogo: Catalogo) -> str:
    ing = catalogo.ingredientes[ingrediente_id]
    return ing.nombre_por_pais.get((pais or "").upper(), ing.nombre)


def nombre_receta(receta_id: str, pais: str | None, catalogo: Catalogo) -> str:
    receta = catalogo.recetas[receta_id]
    return receta.nombres_alternativos.get((pais or "").upper(), receta.nombre)


def formatear_monto(monto: float, pais: str | None, catalogo: Catalogo) -> str:
    """CL → $3.490 · MX → $89.50 · ES → 3,49 €"""
    conf = catalogo.paises[validar_pais(pais, catalogo)]
    decimales = int(conf["decimales"])
    texto = f"{monto:,.{decimales}f}"  # formato inglés: 1,234.56
    texto = texto.replace(",", "§").replace(".", conf["separador_decimal"]).replace("§", conf["separador_miles"])
    if conf["posicion_simbolo"] == "despues":
        return f"{texto} {conf['simbolo']}"
    return f"{conf['simbolo']}{texto}"


def moneda_de(pais: str | None, catalogo: Catalogo) -> str:
    return catalogo.paises[validar_pais(pais, catalogo)]["moneda"]


def proveedores_de(pais: str | None, catalogo: Catalogo) -> list[str]:
    return list(catalogo.paises[validar_pais(pais, catalogo)]["proveedores"])
