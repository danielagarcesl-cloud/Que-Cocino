"""Esquemas Pydantic y carga del catálogo (ingredientes, recetas, precios y configuración)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.configuracion import RAIZ

Nivel = Literal["principiante", "intermedio", "avanzado"]
Restriccion = Literal["ninguna", "vegetariano", "vegano", "pescetariano", "sin_gluten", "sin_lactosa"]
Modo = Literal["solo_lo_que_tengo", "completar_comprando"]
Unidad = Literal["g", "kg", "ml", "l", "un"]

NIVELES = ["principiante", "intermedio", "avanzado"]
RESTRICCIONES = ["ninguna", "vegetariano", "vegano", "pescetariano", "sin_gluten", "sin_lactosa"]
MODOS = ["solo_lo_que_tengo", "completar_comprando"]


# ---------- catálogo ----------
class Ingrediente(BaseModel):
    id: str
    nombre: str
    sinonimos: list[str] = []
    nombre_por_pais: dict[str, str] = {}
    categoria: str
    unidad_base: Literal["g", "ml", "un"]
    etiquetas: list[str] = []
    es_basico: bool = False


class ItemReceta(BaseModel):
    ingrediente_id: str
    cantidad: float
    unidad: Unidad


class Receta(BaseModel):
    id: str
    nombre: str
    nombres_alternativos: dict[str, str] = {}
    cocina_de_origen: str = "varios"
    nivel: Nivel
    tiempo_minutos: int
    porciones_base: int
    ingredientes: list[ItemReceta]
    pasos: list[str] = []


@dataclass
class Catalogo:
    """Todo lo que las funciones puras necesitan saber, en un solo objeto."""
    ingredientes: dict[str, Ingrediente]
    recetas: dict[str, Receta]
    precios: dict[str, dict] = field(default_factory=dict)
    paises: dict[str, dict] = field(default_factory=dict)
    proveedores: dict[str, dict] = field(default_factory=dict)
    _indice: dict[str, str] | None = None  # nombre normalizado -> id (se llena en normalizacion)


def cargar_catalogo(raiz: Path | None = None) -> Catalogo:
    raiz = raiz or RAIZ
    datos, config = raiz / "data", raiz / "config"
    ingredientes = [Ingrediente(**x) for x in json.loads((datos / "ingredientes.json").read_text("utf-8"))]
    recetas = [Receta(**x) for x in json.loads((datos / "recetas.json").read_text("utf-8"))]
    return Catalogo(
        ingredientes={i.id: i for i in ingredientes},
        recetas={r.id: r for r in recetas},
        precios=json.loads((datos / "precios_simulados.json").read_text("utf-8")),
        paises=yaml.safe_load((config / "paises.yaml").read_text("utf-8")),
        proveedores=yaml.safe_load((config / "proveedores.yaml").read_text("utf-8")),
    )


@lru_cache(maxsize=1)
def catalogo_global() -> Catalogo:
    return cargar_catalogo()


# ---------- entradas de usuario ----------
class ItemInventario(BaseModel):
    """Un ingrediente del refrigerador. Si no trae cantidad, se asume suficiente."""
    nombre: str = Field(..., examples=["papa"])
    cantidad: Optional[float] = Field(None, ge=0, examples=[2])
    unidad: Optional[Unidad] = Field(None, examples=["un"])


class Perfil(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pais: Optional[str] = None
    nivel: Optional[Nivel] = None
    restriccion: Optional[Restriccion] = None
    porciones: Optional[int] = Field(None, ge=1, le=50)
    modo: Optional[Modo] = None
    inventario: list[ItemInventario | str] = []


class Favorito(BaseModel):
    model_config = ConfigDict(extra="ignore")
    receta_id: str
    carpeta: str = Field("Favoritas", min_length=1, max_length=40)
    porciones: Optional[int] = Field(None, ge=1, le=50)
    nota: str = Field("", max_length=200)
    guardado_en: str = ""
    veces_preparada: int = Field(0, ge=0)


class Contexto(BaseModel):
    model_config = ConfigDict(extra="ignore")
    perfil: Perfil = Perfil()
    favoritos: list[Favorito] = []
