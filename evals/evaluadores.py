"""Verificaciones automáticas del golden set (sin LLM como juez)."""
from __future__ import annotations

import re

from app.guardian import PATRON_MONTO, normalizar_texto
from app.modelos import Catalogo
from app.recetas import es_compatible

FORMATOS = {  # cómo se ve un monto bien formateado en cada país
    "CL": r"^\$\d{1,3}(\.\d{3})*$", "AR": r"^\$\d{1,3}(\.\d{3})*$", "CO": r"^\$\d{1,3}(\.\d{3})*$",
    "MX": r"^\$\d{1,3}(,\d{3})*\.\d{2}$", "PE": r"^S/\s?\d{1,3}(,\d{3})*\.\d{2}$",
    "ES": r"^\d{1,3}(\.\d{3})*,\d{2}\s?€$", "US": r"^US\$\d{1,3}(,\d{3})*\.\d{2}$", "OTRO": r"^US\$\d{1,3}(,\d{3})*\.\d{2}$",
}


def _palabra(texto: str, palabra: str) -> bool:
    return f" {normalizar_texto(palabra)} " in f" {normalizar_texto(texto)} "


def evaluar(caso: dict, r: dict, catalogo: Catalogo) -> list[tuple[str, bool, str]]:
    """Devuelve [(verificación, pasó, detalle)] para un caso."""
    esp, texto = caso["esperado"], r["respuesta"]
    sugeridas = [x["receta_id"] for x in r["recetas_sugeridas"]]
    exitosas = [h["nombre"] for h in r["traza"]["herramientas"] if not h["error"]]
    res = []

    def chequear(nombre, ok, detalle=""):
        res.append((nombre, bool(ok), detalle))

    if "herramientas_requeridas" in esp:
        faltan = [h for h in esp["herramientas_requeridas"] if h not in r["herramientas_usadas"]]
        chequear("herramientas_requeridas", not faltan, f"faltan {faltan}" if faltan else "")
    if "herramientas_prohibidas_exitosas" in esp:
        usadas = [h for h in esp["herramientas_prohibidas_exitosas"] if h in exitosas]
        chequear("herramientas_prohibidas", not usadas, f"usó {usadas}" if usadas else "")
    if "recetas_requeridas" in esp:
        faltan = [x for x in esp["recetas_requeridas"] if x not in sugeridas]
        chequear("recetas_requeridas", not faltan, f"faltan {faltan}" if faltan else "")
    if "recetas_prohibidas" in esp:
        malas = [x for x in esp["recetas_prohibidas"] if x in sugeridas]
        chequear("recetas_prohibidas", not malas, f"sugirió {malas}" if malas else "")
    if "restriccion_respetada" in esp:
        malas = [x for x in sugeridas if not es_compatible(catalogo.recetas[x], esp["restriccion_respetada"], catalogo)]
        chequear("restriccion_respetada", not malas, f"no cumplen: {malas}" if malas else "")
    if "palabras_requeridas_todas" in esp:
        faltan = [p for p in esp["palabras_requeridas_todas"] if not _palabra(texto, p)]
        chequear("palabras_requeridas", not faltan, f"faltan {faltan}" if faltan else "")
    if "palabras_requeridas_alguna" in esp:
        chequear("alguna_palabra", any(normalizar_texto(p) in normalizar_texto(texto) for p in esp["palabras_requeridas_alguna"]))
    if "palabras_prohibidas" in esp:
        malas = [p for p in esp["palabras_prohibidas"] if _palabra(texto, p)]
        chequear("palabras_prohibidas", not malas, f"usó {malas}" if malas else "")
    if esp.get("contiene_pregunta"):
        chequear("contiene_pregunta", "?" in texto)
    if "formato_moneda" in esp:
        patron = re.compile(FORMATOS[esp["formato_moneda"]])
        malos = [m for m in PATRON_MONTO.findall(texto) if not patron.match(m.strip())]
        chequear("formato_moneda", not malos, f"mal formateados: {malos}" if malos else "")
    if esp.get("sin_montos"):
        chequear("sin_montos", not PATRON_MONTO.findall(texto))
    if esp.get("guardian_sin_plantilla"):
        chequear("guardian", r["traza"]["guardian"] in ("ok", "corregida"), r["traza"]["guardian"])
    if "orden_en_texto" in esp:
        pos = [normalizar_texto(texto).find(normalizar_texto(n)) for n in esp["orden_en_texto"]]
        chequear("orden_en_texto", all(p >= 0 for p in pos) and pos == sorted(pos), str(pos))
    if esp.get("recetas_sugeridas_en_favoritas"):
        favs = {f["receta_id"] for f in caso["entrada"]["contexto"].get("favoritos", [])}
        chequear("solo_favoritas", set(sugeridas) <= favs, str(sugeridas))
    if "favorito_en_contexto" in esp:
        buscado = esp["favorito_en_contexto"]
        ok = any(all(f.get(k) == v for k, v in buscado.items()) for f in r["contexto"]["favoritos"])
        chequear("favorito_en_contexto", ok)
    if "perfil_esperado" in esp:
        perfil = r["contexto"]["perfil"]
        chequear("perfil_esperado", all(perfil.get(k) == v for k, v in esp["perfil_esperado"].items()), str(perfil))
    return res
