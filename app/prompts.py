"""Carga de prompts versionados desde la carpeta prompts/ (los prompts nunca se escriben en el código)."""
from __future__ import annotations

from functools import lru_cache

from app.configuracion import RAIZ

CARPETA = RAIZ / "prompts"


@lru_cache(maxsize=32)
def cargar_prompt(nombre: str, version: str) -> str:
    ruta = CARPETA / f"{nombre}_{version}.md"
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el prompt {ruta.name} en la carpeta prompts/")
    return ruta.read_text(encoding="utf-8").strip()
