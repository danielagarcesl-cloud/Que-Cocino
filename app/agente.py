"""Orquestador de ¿QuéCocino?: herramientas deterministas + bucle agéntico con OpenAI + guardián.

El modelo conversa y decide qué herramienta usar; Python calcula todo y el guardián revisa la respuesta.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app import configuracion
from app.favoritos import guardar_favorito, listar_favoritos, quitar_favorito, repetir_favorito, validar_favoritos
from app.guardian import validar_respuesta
from app.modelos import MODOS, NIVELES, RESTRICCIONES, Catalogo, Contexto, Perfil, catalogo_global
from app.paises import nombre_receta, validar_pais
from app.prompts import cargar_prompt
from app.proveedores import cotizar_compra, proveedores_disponibles
from app.recetas import calcular_faltantes, detalle_receta, obtener_receta, sugerir_menu

MAX_PASOS = 8


# ---------------------------------------------------------------- estado de una conversación
@dataclass
class Estado:
    perfil: Perfil
    favoritos: list[dict]
    catalogo: Catalogo
    resultados: list[dict] = field(default_factory=list)  # [{herramienta, ok, resultado}]
    favoritos_modificados: bool = False

    @classmethod
    def desde_contexto(cls, contexto: dict | Contexto | None, catalogo: Catalogo) -> "Estado":
        ctx = contexto if isinstance(contexto, Contexto) else Contexto(**(contexto or {}))
        favoritos = validar_favoritos([f.model_dump() for f in ctx.favoritos], catalogo)["favoritos"]
        return cls(perfil=ctx.perfil, favoritos=favoritos, catalogo=catalogo)

    def contexto(self) -> dict:
        return {"perfil": self.perfil.model_dump(), "favoritos": self.favoritos}

    def resumen_para_modelo(self) -> dict:
        """Perfil completo, pero solo un resumen de las favoritas (sin notas): ahorra tokens y evita inyecciones."""
        return {
            "perfil": self.perfil.model_dump(),
            "favoritas": [{"receta_id": f["receta_id"], "nombre": nombre_receta(f["receta_id"], self.perfil.pais, self.catalogo),
                           "carpeta": f["carpeta"]} for f in self.favoritos],
        }


# ---------------------------------------------------------------- utilidades
def _actualizar_perfil(estado: Estado, campos: dict) -> None:
    datos = estado.perfil.model_dump()
    for clave in ("pais", "nivel", "restriccion", "porciones", "modo", "inventario"):
        if campos.get(clave) not in (None, "", []):
            datos[clave] = campos[clave]
    if datos.get("pais"):
        datos["pais"] = validar_pais(datos["pais"], estado.catalogo)
    estado.perfil = Perfil(**datos)


def _requerir(estado: Estado, *campos: str) -> None:
    faltan = [c for c in campos if getattr(estado.perfil, c) in (None, "")]
    if faltan:
        raise ValueError(f"Falta conocer: {', '.join(faltan)}. Pregúntaselo al usuario antes de continuar.")


def _pais(estado: Estado) -> str:
    return estado.perfil.pais or configuracion.pais_por_defecto()


def _porciones(estado: Estado, args: dict, receta_id: str | None = None) -> int:
    if args.get("porciones"):
        return int(args["porciones"])
    if estado.perfil.porciones:
        return estado.perfil.porciones
    return obtener_receta(receta_id, estado.catalogo).porciones_base if receta_id else 4


# ---------------------------------------------------------------- ejecutores (sin LLM)
def h_actualizar_perfil(args: dict, estado: Estado) -> dict:
    _actualizar_perfil(estado, args.get("campos", args))
    faltan = [c for c in ("nivel", "restriccion", "porciones") if getattr(estado.perfil, c) is None]
    return {"perfil": estado.perfil.model_dump(), "faltan": faltan}


def h_sugerir_menu(args: dict, estado: Estado) -> dict:
    _actualizar_perfil(estado, args)
    _requerir(estado, "nivel", "restriccion")
    p = estado.perfil
    modo = p.modo or "completar_comprando"
    recetas = sugerir_menu(p.inventario, p.nivel, p.restriccion, p.porciones or 4, estado.catalogo, modo=modo,
                           pais=_pais(estado), max_resultados=int(args.get("max_resultados") or 5))
    return {"recetas": recetas, "porciones": p.porciones or 4, "modo": modo, "pais": _pais(estado)}


def h_detalle_receta(args: dict, estado: Estado) -> dict:
    rid = args["receta_id"]
    return detalle_receta(rid, _porciones(estado, args, rid), args.get("pais") or _pais(estado), estado.catalogo)


def h_calcular_faltantes(args: dict, estado: Estado) -> dict:
    rid = args["receta_id"]
    receta = obtener_receta(rid, estado.catalogo)
    inventario = args.get("inventario") or estado.perfil.inventario
    porciones = _porciones(estado, args, rid)
    return {"receta_id": rid, "porciones": porciones,
            "faltantes": calcular_faltantes(receta, inventario, porciones, estado.catalogo, _pais(estado))}


def h_armar_carrito(args: dict, estado: Estado) -> dict:
    _actualizar_perfil(estado, {"pais": args.get("pais")})
    rid = args["receta_id"]
    receta = obtener_receta(rid, estado.catalogo)
    inventario = args.get("inventario") or estado.perfil.inventario
    porciones = _porciones(estado, args, rid)
    faltantes = calcular_faltantes(receta, inventario, porciones, estado.catalogo, _pais(estado))
    carrito = cotizar_compra(faltantes, _pais(estado), args.get("proveedor"), estado.catalogo)
    return {"receta_id": rid, "nombre": nombre_receta(rid, _pais(estado), estado.catalogo), "porciones": porciones,
            "faltantes": faltantes, "carrito": carrito}


def h_listar_opciones(args: dict, estado: Estado) -> dict:
    c = estado.catalogo
    return {"niveles": NIVELES, "restricciones": RESTRICCIONES, "modos": MODOS,
            "paises": {k: v["nombre"] for k, v in c.paises.items()},
            "proveedores_por_pais": {k: [p["id"] for p in proveedores_disponibles(k, c)] for k in c.paises}}


def h_guardar_favorito(args: dict, estado: Estado) -> dict:
    rid = args["receta_id"]
    estado.favoritos = guardar_favorito(estado.favoritos, rid, estado.catalogo, carpeta=args.get("carpeta"),
                                        porciones=args.get("porciones"), nota=args.get("nota") or "")
    estado.favoritos_modificados = True
    guardada = next(f for f in estado.favoritos if f["receta_id"] == rid
                    and f["carpeta"] == ((args.get("carpeta") or "").strip() or "Favoritas"))
    return {"ok": True, "guardado": {**guardada, "nombre": nombre_receta(rid, _pais(estado), estado.catalogo)},
            "total_favoritas": len(estado.favoritos)}


def h_quitar_favorito(args: dict, estado: Estado) -> dict:
    estado.favoritos = quitar_favorito(estado.favoritos, args["receta_id"], args.get("carpeta"))
    estado.favoritos_modificados = True
    return {"ok": True, "quitado": args["receta_id"], "total_favoritas": len(estado.favoritos)}


def h_listar_favoritos(args: dict, estado: Estado) -> dict:
    inventario = estado.perfil.inventario if args.get("usar_inventario") else None
    return {"favoritas": listar_favoritos(estado.favoritos, estado.perfil, estado.catalogo,
                                          carpeta=args.get("carpeta"), inventario=inventario)}


def h_repetir_favorito(args: dict, estado: Estado) -> dict:
    rid = args["receta_id"]
    r = repetir_favorito(estado.favoritos, rid, estado.perfil.inventario, _pais(estado), estado.catalogo,
                         porciones=args.get("porciones"), carpeta=args.get("carpeta"))
    estado.favoritos = r["favoritos"]
    estado.favoritos_modificados = True
    r["carrito"] = cotizar_compra(r["faltantes"], _pais(estado), args.get("proveedor"), estado.catalogo)
    receta = estado.catalogo.recetas[rid]
    from app.favoritos import _compatible  # misma regla que en la lista de favoritas
    r["compatible_con_perfil"] = _compatible(receta, estado.perfil, estado.catalogo)
    return {k: v for k, v in r.items() if k != "favoritos"}


EJECUTORES = {
    "actualizar_perfil": h_actualizar_perfil,
    "sugerir_menu": h_sugerir_menu,
    "detalle_receta": h_detalle_receta,
    "calcular_faltantes": h_calcular_faltantes,
    "armar_carrito": h_armar_carrito,
    "listar_opciones": h_listar_opciones,
    "guardar_favorito": h_guardar_favorito,
    "quitar_favorito": h_quitar_favorito,
    "listar_favoritos": h_listar_favoritos,
    "repetir_favorito": h_repetir_favorito,
}


# ---------------------------------------------------------------- catálogo de herramientas (formato OpenAI)
def _f(nombre, descripcion, propiedades=None, requeridos=None):
    return {"type": "function", "function": {"name": nombre, "description": descripcion, "parameters": {
        "type": "object", "properties": propiedades or {}, "required": requeridos or []}}}


_INVENTARIO = {"type": "array", "description": "Ingredientes disponibles. Texto simple o {nombre, cantidad, unidad}.",
               "items": {"anyOf": [{"type": "string"}, {"type": "object", "properties": {
                   "nombre": {"type": "string"}, "cantidad": {"type": "number"},
                   "unidad": {"type": "string", "enum": ["g", "kg", "ml", "l", "un"]}}, "required": ["nombre"]}]}}
_RECETA = {"type": "string", "description": "id de la receta, tal como lo devolvió otra herramienta"}
_PORCIONES = {"type": "integer", "minimum": 1, "maximum": 50}

HERRAMIENTAS = [
    _f("actualizar_perfil", "Guarda en el perfil los datos que el usuario entregó (país, nivel, restricción, porciones, modo, inventario). Devuelve qué datos faltan.",
       {"campos": {"type": "object", "properties": {
           "pais": {"type": "string", "description": "Código ISO: CL, AR, MX, CO, PE, ES, US u OTRO"},
           "nivel": {"type": "string", "enum": NIVELES}, "restriccion": {"type": "string", "enum": RESTRICCIONES},
           "porciones": _PORCIONES, "modo": {"type": "string", "enum": MODOS}, "inventario": _INVENTARIO}}},
       ["campos"]),
    _f("sugerir_menu", "Ranking de recetas del catálogo según inventario, nivel, restricción, porciones, modo y país. Requiere nivel y restricción.",
       {"inventario": _INVENTARIO, "nivel": {"type": "string", "enum": NIVELES},
        "restriccion": {"type": "string", "enum": RESTRICCIONES}, "porciones": _PORCIONES,
        "modo": {"type": "string", "enum": MODOS}, "pais": {"type": "string"},
        "max_resultados": {"type": "integer", "minimum": 1, "maximum": 10}}),
    _f("detalle_receta", "Ingredientes escalados (con nombres locales) y pasos de una receta.",
       {"receta_id": _RECETA, "porciones": _PORCIONES, "pais": {"type": "string"}}, ["receta_id"]),
    _f("calcular_faltantes", "Ingredientes que faltan para preparar una receta con el inventario actual.",
       {"receta_id": _RECETA, "inventario": _INVENTARIO, "porciones": _PORCIONES}, ["receta_id"]),
    _f("armar_carrito", "Carrito de lo que falta con precios referenciales, total formateado y enlaces de búsqueda del proveedor.",
       {"receta_id": _RECETA, "inventario": _INVENTARIO, "porciones": _PORCIONES, "pais": {"type": "string"},
        "proveedor": {"type": "string", "description": "id del proveedor; por defecto 'simulado'"}}, ["receta_id"]),
    _f("listar_opciones", "Niveles, restricciones, modos, países y proveedores válidos."),
    _f("guardar_favorito", "Guarda una receta en una carpeta de favoritas del usuario (por defecto 'Favoritas').",
       {"receta_id": _RECETA, "carpeta": {"type": "string", "maxLength": 40}, "porciones": _PORCIONES,
        "nota": {"type": "string", "maxLength": 200}}, ["receta_id"]),
    _f("quitar_favorito", "Quita una receta de las favoritas (de una carpeta o de todas).",
       {"receta_id": _RECETA, "carpeta": {"type": "string"}}, ["receta_id"]),
    _f("listar_favoritos", "Lista las favoritas del usuario, marcando si cumplen su perfil. Con usar_inventario=true las ordena según lo que tiene hoy.",
       {"carpeta": {"type": "string"}, "usar_inventario": {"type": "boolean"}}),
    _f("repetir_favorito", "Para volver a preparar una favorita: detalle, faltantes y carrito con las porciones guardadas.",
       {"receta_id": _RECETA, "porciones": _PORCIONES, "proveedor": {"type": "string"}}, ["receta_id"]),
]


def ejecutar_herramienta(nombre: str, argumentos, estado: Estado | None = None) -> tuple[str, bool]:
    """Ejecuta una herramienta. Si falla, devuelve {"error": ...} para que el modelo lo lea y se corrija."""
    estado = estado or Estado(perfil=Perfil(), favoritos=[], catalogo=catalogo_global())
    try:
        args = json.loads(argumentos) if isinstance(argumentos, str) else dict(argumentos or {})
        if nombre not in EJECUTORES:
            raise ValueError(f"Herramienta desconocida: {nombre}")
        resultado = EJECUTORES[nombre](args, estado)
        estado.resultados.append({"herramienta": nombre, "ok": True, "resultado": resultado})
        return json.dumps(resultado, ensure_ascii=False), False
    except KeyError as e:
        error = str(e).strip("'\"")
    except Exception as e:  # noqa: BLE001 - cualquier error vuelve al modelo como dato
        error = str(e)
    estado.resultados.append({"herramienta": nombre, "ok": False, "resultado": {"error": error}})
    return json.dumps({"error": error}, ensure_ascii=False), True


# ---------------------------------------------------------------- respuesta de plantilla (red de seguridad)
def respuesta_plantilla(estado: Estado) -> str:
    ultimo = {r["herramienta"]: r["resultado"] for r in estado.resultados if r["ok"]}
    partes = []
    if "sugerir_menu" in ultimo and ultimo["sugerir_menu"]["recetas"]:
        lineas = []
        for r in ultimo["sugerir_menu"]["recetas"][:3]:
            falta = ", ".join(f["nombre"] for f in r["faltantes"]) or "nada"
            lineas.append(f"{r['nombre']} (tienes el {round(r['cobertura'] * 100)} % de los ingredientes; te falta: {falta})")
        partes.append("Con lo que tienes te sugiero: " + "; ".join(lineas) + ".")
    if "listar_favoritos" in ultimo and ultimo["listar_favoritos"]["favoritas"]:
        aptas = [f["nombre"] for f in ultimo["listar_favoritos"]["favoritas"] if f["compatible_con_perfil"]]
        if aptas:
            partes.append("De tus favoritas, estas cumplen tu perfil: " + ", ".join(aptas[:5]) + ".")
    for clave in ("armar_carrito", "repetir_favorito"):
        if clave in ultimo:
            partes.append(f"Lo que falta suma {ultimo[clave]['carrito']['total_formateado']} (precios referenciales).")
    if not partes:
        return ("No pude armar una respuesta segura. ¿Me cuentas tu nivel de cocina, tu restricción alimentaria "
                "y qué tienes en el refrigerador?")
    return " ".join(partes)


# ---------------------------------------------------------------- bucle agéntico
def _mensaje_assistant(msg) -> dict:
    return {"role": "assistant", "content": msg.content or "",
            "tool_calls": [{"id": tc.id, "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                           for tc in msg.tool_calls]}


def crear_cliente():
    from openai import OpenAI
    return OpenAI()


def responder(mensaje: str, contexto: dict | None = None, cliente=None, catalogo: Catalogo | None = None) -> dict:
    catalogo = catalogo or catalogo_global()
    cliente = cliente or crear_cliente()
    estado = Estado.desde_contexto(contexto, catalogo)
    version = configuracion.version_prompt_agente()
    mensajes = [
        {"role": "system", "content": cargar_prompt("agente_sistema", version)},
        {"role": "user", "content": f"{mensaje}\n\nContexto (JSON): {json.dumps(estado.resumen_para_modelo(), ensure_ascii=False)}"},
    ]
    usadas: list[str] = []
    tokens = [0, 0]
    rechazos = 0
    texto, estado_guardian, recetas = None, "tope_pasos", []

    for _ in range(MAX_PASOS):
        resp = cliente.chat.completions.create(model=configuracion.modelo(), messages=mensajes,
                                               tools=HERRAMIENTAS, temperature=0.3)
        uso = getattr(resp, "usage", None)
        tokens[0] += int(getattr(uso, "prompt_tokens", 0) or 0)
        tokens[1] += int(getattr(uso, "completion_tokens", 0) or 0)
        msg = resp.choices[0].message

        if msg.tool_calls:
            mensajes.append(_mensaje_assistant(msg))
            for tc in msg.tool_calls:
                contenido, _ = ejecutar_herramienta(tc.function.name, tc.function.arguments, estado)
                usadas.append(tc.function.name)
                mensajes.append({"role": "tool", "tool_call_id": tc.id, "content": contenido})
            continue

        borrador = msg.content or ""
        revision = validar_respuesta(borrador, estado.resultados, estado.perfil, catalogo)
        if revision["ok"]:
            texto, estado_guardian, recetas = borrador, ("ok" if rechazos == 0 else "corregida"), revision["recetas_sugeridas"]
            break
        rechazos += 1
        if rechazos > 1:
            estado_guardian = "plantilla"
            break
        mensajes.append({"role": "assistant", "content": borrador})
        correccion = cargar_prompt("guardian_correccion", "v1").replace(
            "{problemas}", "\n".join(f"- {p}" for p in revision["problemas"]))
        mensajes.append({"role": "system", "content": correccion})

    if texto is None:
        texto = respuesta_plantilla(estado)
        recetas = validar_respuesta(texto, estado.resultados, estado.perfil, catalogo)["recetas_sugeridas"]

    return {
        "respuesta": texto,
        "herramientas_usadas": usadas,
        "recetas_sugeridas": [{"receta_id": r, "nombre": nombre_receta(r, estado.perfil.pais, catalogo)} for r in recetas],
        "contexto": estado.contexto(),
        "traza": {
            "pasos": len([m for m in mensajes if m["role"] == "assistant"]) + 1,
            "herramientas": [{"nombre": r["herramienta"], "error": not r["ok"]} for r in estado.resultados],
            "favoritos_modificados": estado.favoritos_modificados,
            "guardian": estado_guardian,
            "tokens_entrada": tokens[0],
            "tokens_salida": tokens[1],
            "costo_estimado_usd": configuracion.costo_usd(*tokens),
        },
        "version_prompt": version,
        "modelo": configuracion.modelo(),
    }
