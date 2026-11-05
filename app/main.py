"""API FastAPI de ¿QuéCocino?."""
from __future__ import annotations

from typing import Literal, Optional

import openai

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import agente, configuracion, vision
from app.favoritos import guardar_favorito, listar_favoritos, quitar_favorito, repetir_favorito, validar_favoritos
from app.limites import LimiteSuperado, limitador
from app.modelos import (MODOS, NIVELES, RESTRICCIONES, Favorito, ItemInventario, Modo, Nivel, Perfil,
                         Restriccion, catalogo_global)
from app.normalizacion import resolver_ingrediente
from app.paises import nombre_local, validar_pais
from app.proveedores import cotizar_compra, proveedores_disponibles
from app.recetas import calcular_faltantes, detalle_receta, obtener_receta, sugerir_menu

CARPETA_STATIC = configuracion.RAIZ / "app" / "static"

app = FastAPI(
    title="¿QuéCocino? API",
    version=configuracion.VERSION_APP,
    description="Recetas caseras con lo que hay en tu refri, para todo el mundo de habla hispana. "
                "Equipo: " + " · ".join(configuracion.EQUIPO),
)
app.add_middleware(CORSMiddleware, allow_origins=configuracion.origenes_permitidos(),
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=CARPETA_STATIC), name="static")

# Clientes de OpenAI inyectables (los tests los reemplazan por clientes falsos)
app.state.cliente_openai = None


@app.exception_handler(openai.APIError)
def _error_openai(request: Request, error: openai.APIError):
    """Traduce los errores del proveedor de IA a un mensaje claro, sin mostrar detalles internos."""
    codigo = getattr(error, "code", None) or (getattr(error, "body", None) or {}).get("code")
    if codigo in ("insufficient_quota", "credit_balance_exhausted") or "quota" in str(error).lower():
        mensaje = ("El asistente de IA no tiene saldo disponible en este momento. "
                   "Mientras tanto, escribe tus ingredientes a mano en la pestaña Cocinar.")
    elif isinstance(error, openai.RateLimitError):
        mensaje = "El asistente de IA está muy ocupado. Espera un minuto e intenta de nuevo."
    elif isinstance(error, openai.AuthenticationError):
        mensaje = "La llave del asistente de IA no es válida. Revisa OPENAI_API_KEY en el servidor."
    else:
        mensaje = "El asistente de IA no respondió. Intenta de nuevo en unos minutos."
    return JSONResponse(status_code=503, content={"detail": mensaje})


def _cliente():
    if app.state.cliente_openai is not None:
        return app.state.cliente_openai
    if not configuracion.hay_llave_openai():
        raise HTTPException(503, "Falta configurar OPENAI_API_KEY en el servidor.")
    return agente.crear_cliente()


def _ip(request: Request) -> str:
    reenviada = request.headers.get("x-forwarded-for")
    return reenviada.split(",")[0].strip() if reenviada else (request.client.host if request.client else "desconocida")


def _limitar(request: Request, tipo: str):
    try:
        limitador.registrar(_ip(request), tipo)
    except LimiteSuperado:
        raise HTTPException(429, "Llegaste al límite de uso de hoy. ¡Vuelve mañana! Mientras tanto puedes "
                                 "escribir tus ingredientes a mano.")


def _pais(pais: str | None) -> str:
    try:
        return validar_pais(pais or configuracion.pais_por_defecto(), catalogo_global())
    except ValueError as e:
        raise HTTPException(422, str(e))


# ---------------------------------------------------------------- modelos de entrada
EJEMPLO_INV = ["papa", "huevo", "cebolla", "queso"]


class PedidoMenu(BaseModel):
    inventario: list[ItemInventario | str] = Field(..., examples=[EJEMPLO_INV])
    nivel: Nivel = Field(..., examples=["avanzado"])
    restriccion: Restriccion = Field(..., examples=["vegetariano"])
    porciones: int = Field(4, ge=1, le=50)
    modo: Modo = "completar_comprando"
    pais: str = Field("OTRO", examples=["CL"])
    max_resultados: int = Field(5, ge=1, le=10)


class PedidoCarrito(BaseModel):
    receta_id: str = Field(..., examples=["tortilla_de_papas"])
    inventario: list[ItemInventario | str] = Field(default_factory=list, examples=[EJEMPLO_INV])
    porciones: int = Field(4, ge=1, le=50)
    pais: str = Field("OTRO", examples=["CL"])
    proveedor: Optional[str] = Field(None, examples=["simulado"])


class PedidoResolver(BaseModel):
    textos: list[str] = Field(..., examples=[["Patatas", "aguacate", "cosa rara"]])
    pais: str = "OTRO"


class PedidoAgente(BaseModel):
    mensaje: str = Field(..., min_length=1, max_length=1000, examples=["¿Qué cocino hoy con lo que tengo?"])
    contexto: Optional[dict] = Field(None, examples=[{"perfil": {"pais": "CL", "nivel": "principiante",
                                                                 "restriccion": "ninguna", "porciones": 2,
                                                                 "inventario": EJEMPLO_INV}, "favoritos": []}])


class PedidoFavoritos(BaseModel):
    favoritos: list[Favorito] = Field(default_factory=list)


class PedidoGuardar(PedidoFavoritos):
    receta_id: str = Field(..., examples=["tortilla_de_papas"])
    carpeta: Optional[str] = Field(None, max_length=40, examples=["Cumpleaños"])
    porciones: Optional[int] = Field(None, ge=1, le=50)
    nota: str = Field("", max_length=200)


class PedidoQuitar(PedidoFavoritos):
    receta_id: str
    carpeta: Optional[str] = None


class PedidoListar(PedidoFavoritos):
    perfil: Perfil = Perfil()
    carpeta: Optional[str] = None
    inventario: Optional[list[ItemInventario | str]] = None


class PedidoRepetir(PedidoFavoritos):
    receta_id: str
    inventario: list[ItemInventario | str] = Field(default_factory=list)
    pais: str = "OTRO"
    porciones: Optional[int] = Field(None, ge=1, le=50)
    proveedor: Optional[str] = None
    carpeta: Optional[str] = None


def _favs(pedido: PedidoFavoritos) -> list[dict]:
    return [f.model_dump() for f in pedido.favoritos]


# ---------------------------------------------------------------- rutas
@app.get("/health")
def salud():
    return {"status": "ok", "version": configuracion.VERSION_APP, "entorno": configuracion.entorno(),
            "version_prompt": configuracion.version_prompt_agente(), "equipo": configuracion.EQUIPO}


@app.get("/opciones")
def opciones():
    cat = catalogo_global()
    return {"niveles": NIVELES, "restricciones": RESTRICCIONES, "modos": MODOS,
            "paises": [{"codigo": k, "nombre": v["nombre"], "moneda": v["moneda"],
                        "proveedores": proveedores_disponibles(k, cat)} for k, v in cat.paises.items()]}


@app.get("/ingredientes")
def ingredientes(pais: str = "OTRO"):
    cat, pais = catalogo_global(), _pais(pais)
    return [{"id": i.id, "nombre": nombre_local(i.id, pais, cat), "es_basico": i.es_basico}
            for i in sorted(cat.ingredientes.values(), key=lambda x: nombre_local(x.id, pais, cat))]


@app.post("/ingredientes/resolver")
def resolver(pedido: PedidoResolver):
    cat, pais = catalogo_global(), _pais(pedido.pais)
    reconocidos, no_reconocidos = [], []
    for t in pedido.textos:
        i = resolver_ingrediente(t, cat)
        if i and i not in reconocidos:
            reconocidos.append(i)
        elif not i:
            no_reconocidos.append(t)
    return {"reconocidos": reconocidos, "no_reconocidos": no_reconocidos,
            "nombres": {i: nombre_local(i, pais, cat) for i in reconocidos}}


@app.post("/ingredientes/detectar")
async def detectar(request: Request, imagen: UploadFile = File(...), pais: str = Form("OTRO")):
    pais = _pais(pais)
    contenido = await imagen.read()
    mime = imagen.content_type or ""
    if mime not in vision.TIPOS_PERMITIDOS:
        raise HTTPException(415, "Tipo de imagen no permitido. Usa JPG, PNG o WEBP.")
    if len(contenido) > configuracion.max_imagen_bytes():
        raise HTTPException(413, "La imagen es demasiado grande.")
    cliente = _cliente()
    _limitar(request, "fotos")
    try:
        return vision.detectar_ingredientes(contenido, mime, pais=pais, cliente=cliente)
    finally:
        del contenido  # la imagen no se guarda en ninguna parte


@app.post("/menu/sugerir")
def menu(pedido: PedidoMenu):
    pais = _pais(pedido.pais)
    try:
        recetas = sugerir_menu(pedido.inventario, pedido.nivel, pedido.restriccion, pedido.porciones,
                               catalogo_global(), modo=pedido.modo, pais=pais, max_resultados=pedido.max_resultados)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"recetas": recetas, "pais": pais, "porciones": pedido.porciones, "modo": pedido.modo}


@app.post("/carrito")
def carrito(pedido: PedidoCarrito):
    cat, pais = catalogo_global(), _pais(pedido.pais)
    try:
        receta = obtener_receta(pedido.receta_id, cat)
    except KeyError as e:
        raise HTTPException(404, str(e).strip("'\""))
    try:
        faltantes = calcular_faltantes(receta, pedido.inventario, pedido.porciones, cat, pais)
        return {"receta_id": receta.id, "faltantes": faltantes,
                **cotizar_compra(faltantes, pais, pedido.proveedor or configuracion.proveedor_por_defecto(), cat)}
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/recetas/{receta_id}")
def receta(receta_id: str, porciones: Optional[int] = None, pais: str = "OTRO"):
    try:
        return detalle_receta(receta_id, porciones, _pais(pais), catalogo_global())
    except KeyError as e:
        raise HTTPException(404, str(e).strip("'\""))


@app.post("/favoritos/guardar")
def favoritos_guardar(pedido: PedidoGuardar):
    try:
        return {"favoritos": guardar_favorito(_favs(pedido), pedido.receta_id, catalogo_global(),
                                              carpeta=pedido.carpeta, porciones=pedido.porciones, nota=pedido.nota)}
    except KeyError as e:
        raise HTTPException(404, str(e).strip("'\""))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/favoritos/quitar")
def favoritos_quitar(pedido: PedidoQuitar):
    try:
        return {"favoritos": quitar_favorito(_favs(pedido), pedido.receta_id, pedido.carpeta)}
    except KeyError as e:
        raise HTTPException(404, str(e).strip("'\""))


@app.post("/favoritos/listar")
def favoritos_listar(pedido: PedidoListar):
    cat = catalogo_global()
    validados = validar_favoritos(_favs(pedido), cat)
    return {"favoritas": listar_favoritos(validados["favoritos"], pedido.perfil, cat, pedido.carpeta, pedido.inventario),
            "favoritos": validados["favoritos"], "descartados": validados["descartados"]}


@app.post("/favoritos/repetir")
def favoritos_repetir(pedido: PedidoRepetir):
    cat, pais = catalogo_global(), _pais(pedido.pais)
    try:
        r = repetir_favorito(_favs(pedido), pedido.receta_id, pedido.inventario, pais, cat,
                             porciones=pedido.porciones, carpeta=pedido.carpeta)
        r["carrito"] = cotizar_compra(r["faltantes"], pais, pedido.proveedor or "simulado", cat)
        return r
    except KeyError as e:
        raise HTTPException(404, str(e).strip("'\""))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/agente")
def preguntar_al_agente(pedido: PedidoAgente, request: Request):
    cliente = _cliente()
    _limitar(request, "agente")
    try:
        return agente.responder(pedido.mensaje, pedido.contexto, cliente=cliente)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(CARPETA_STATIC / "index.html")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    # servido desde la raíz para que pueda controlar toda la app
    return FileResponse(CARPETA_STATIC / "sw.js", media_type="application/javascript")
