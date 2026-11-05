"""Guardián: valida la respuesta final del orquestador antes de entregarla (Python, sin LLM).

Revisa que:
 1. toda receta del catálogo nombrada haya salido de una herramienta;
 2. las recetas nombradas cumplan la restricción y el nivel (o que el texto advierta que no cumplen);
 3. todo monto con símbolo de moneda coincida con uno calculado por las herramientas;
 4. si hubo carrito, se avise que los precios son referenciales;
 5. no se afirme haber guardado o quitado una favorita sin una llamada exitosa a la herramienta.
"""
from __future__ import annotations

import re
import unicodedata

from app.modelos import Catalogo, Perfil
from app.recetas import es_compatible, nivel_permitido

PATRON_MONTO = re.compile(r"(?:US\$|S/|\$)\s?\d+(?:[.,]\d+)*|\d+(?:[.,]\d+)*\s?€")
PATRON_AFIRMA_FAVORITA = re.compile(
    r"\b(guarde|la guarde|lo guarde|agregue|anadi|quite|elimine|movi|quedo guardad[ao]|ya esta guardad[ao]"
    r"|ya esta en tus favorit[ao]s|quedo en tu carpeta)\b")
ADVERTENCIAS = ("no cumple", "ya no es apta", "no es apta", "no es compatible", "no apta", "no te la recomiendo",
                "no la recomiendo", "no sirve para", "no es adecuada", "no corresponde a tu")
HERRAMIENTAS_CARRITO = {"armar_carrito", "repetir_favorito"}
HERRAMIENTAS_FAVORITAS = {"guardar_favorito", "quitar_favorito"}


def normalizar_texto(texto: str) -> str:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9$€/ ]+", " ", t).split())


def _recorrer(obj, clave_buscada=None, sufijo=None):
    """Recolecta valores de un JSON anidado por clave exacta o por sufijo de clave."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if (clave_buscada and k == clave_buscada) or (sufijo and k.endswith(sufijo)):
                if isinstance(v, (str, int, float)):
                    yield v
            yield from _recorrer(v, clave_buscada, sufijo)
    elif isinstance(obj, list):
        for x in obj:
            yield from _recorrer(x, clave_buscada, sufijo)


def recetas_mencionadas(texto: str, catalogo: Catalogo) -> list[str]:
    norm = f" {normalizar_texto(texto)} "
    encontradas = []
    for receta in catalogo.recetas.values():
        nombres = {receta.nombre, *receta.nombres_alternativos.values()}
        if any(f" {normalizar_texto(n)} " in norm for n in nombres):
            encontradas.append(receta.id)
    return encontradas


def _compatible(receta_id: str, perfil: Perfil, catalogo: Catalogo) -> bool:
    receta = catalogo.recetas[receta_id]
    return (es_compatible(receta, perfil.restriccion or "ninguna", catalogo)
            and nivel_permitido(receta.nivel, perfil.nivel or "avanzado"))


def validar_respuesta(texto: str, resultados: list[dict], perfil: Perfil, catalogo: Catalogo) -> dict:
    problemas: list[str] = []
    exitosos = [r for r in resultados if r.get("ok")]
    devueltas = {str(v) for r in exitosos for v in _recorrer(r.get("resultado"), clave_buscada="receta_id")}
    mencionadas = recetas_mencionadas(texto, catalogo)
    norm = normalizar_texto(texto)
    advierte = any(a in norm for a in ADVERTENCIAS)

    # 1 y 2. recetas del catálogo y compatibles
    for rid in mencionadas:
        nombre = catalogo.recetas[rid].nombre
        if rid not in devueltas:
            problemas.append(f"Mencionaste «{nombre}», pero ninguna herramienta la devolvió en esta conversación.")
        elif not _compatible(rid, perfil, catalogo) and not advierte:
            problemas.append(f"«{nombre}» no cumple la restricción o el nivel del usuario y no lo advertiste.")

    # 3. montos iguales a los calculados
    permitidos = {re.sub(r"\s", "", str(v)) for r in exitosos for v in _recorrer(r.get("resultado"), sufijo="_formateado")}
    for monto in PATRON_MONTO.findall(texto):
        if re.sub(r"\s", "", monto) not in permitidos:
            problemas.append(f"El monto {monto.strip()} no coincide con ningún precio calculado por las herramientas.")

    # 4. aviso de precios referenciales
    if any(r["herramienta"] in HERRAMIENTAS_CARRITO for r in exitosos) and "referencial" not in norm:
        problemas.append("Hubo carrito, pero no aclaraste que los precios son referenciales.")

    # 5. favoritas confirmadas
    if PATRON_AFIRMA_FAVORITA.search(norm) and not any(r["herramienta"] in HERRAMIENTAS_FAVORITAS for r in exitosos):
        problemas.append("Afirmaste haber guardado o quitado una favorita sin que la herramienta lo confirmara.")

    compatibles = [rid for rid in mencionadas if rid in devueltas and _compatible(rid, perfil, catalogo)]
    return {"ok": not problemas, "problemas": problemas, "recetas_sugeridas": compatibles}
