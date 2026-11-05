"""Agente de percepción: detecta ingredientes en una foto con el modelo de visión.

La imagen se procesa en memoria y nunca se guarda en disco ni en logs.
"""
from __future__ import annotations

import base64
import json

from app import configuracion
from app.modelos import Catalogo, catalogo_global
from app.normalizacion import resolver_ingrediente
from app.paises import nombre_local
from app.prompts import cargar_prompt

TIPOS_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}
CONFIANZA_MINIMA = 0.5

ESQUEMA = {
    "name": "ingredientes_detectados",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["ingredientes"],
        "properties": {
            "ingredientes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["nombre", "confianza"],
                    "properties": {"nombre": {"type": "string"}, "confianza": {"type": "number"}},
                },
            }
        },
    },
}


class ErrorTipoImagen(ValueError):
    pass


class ErrorTamanoImagen(ValueError):
    pass


def crear_cliente():
    from openai import OpenAI  # import tardío: los tests no lo necesitan
    return OpenAI()


def detectar_ingredientes(imagen_bytes: bytes, mime: str, pais: str | None = None, cliente=None,
                          catalogo: Catalogo | None = None) -> dict:
    # 1. validar ANTES de llamar al modelo
    if mime not in TIPOS_PERMITIDOS:
        raise ErrorTipoImagen(f"Tipo de imagen no permitido: {mime}. Usa JPG, PNG o WEBP.")
    if len(imagen_bytes) > configuracion.max_imagen_bytes():
        raise ErrorTamanoImagen("La imagen supera el tamaño máximo permitido.")
    catalogo = catalogo or catalogo_global()
    cliente = cliente or crear_cliente()

    # 2. llamar al modelo con salida estructurada estricta
    imagen_b64 = base64.b64encode(imagen_bytes).decode("ascii")
    respuesta = cliente.chat.completions.create(
        model=configuracion.modelo(),
        messages=[
            {"role": "system", "content": cargar_prompt("vision", configuracion.version_prompt_vision())},
            {"role": "user", "content": [
                {"type": "text", "text": "Lista los alimentos visibles en esta imagen."},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{imagen_b64}"}},
            ]},
        ],
        response_format={"type": "json_schema", "json_schema": ESQUEMA},
        temperature=0,
    )
    del imagen_b64
    datos = json.loads(respuesta.choices[0].message.content or '{"ingredientes": []}')

    # 3 y 4. normalizar y separar reconocidos, no reconocidos y dudosos
    reconocidos, no_reconocidos, dudosos = [], [], []
    for item in datos.get("ingredientes", []):
        nombre = str(item.get("nombre", "")).strip()
        confianza = float(item.get("confianza", 0))
        ing_id = resolver_ingrediente(nombre, catalogo)
        if confianza < CONFIANZA_MINIMA:
            destino, valor = dudosos, ing_id or nombre
        elif ing_id:
            destino, valor = reconocidos, ing_id
        else:
            destino, valor = no_reconocidos, nombre
        if valor and valor not in destino:
            destino.append(valor)

    uso = getattr(respuesta, "usage", None)
    entrada = int(getattr(uso, "prompt_tokens", 0) or 0)
    salida = int(getattr(uso, "completion_tokens", 0) or 0)
    ids = [x for x in reconocidos + dudosos if x in catalogo.ingredientes]
    return {
        "reconocidos": reconocidos,
        "no_reconocidos": no_reconocidos,
        "dudosos": dudosos,
        "nombres": {i: nombre_local(i, pais, catalogo) for i in ids},
        "traza": {"tokens_entrada": entrada, "tokens_salida": salida,
                  "costo_estimado_usd": configuracion.costo_usd(entrada, salida),
                  "version_prompt": configuracion.version_prompt_vision()},
    }
