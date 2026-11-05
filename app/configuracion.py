"""Lectura de variables de entorno en un solo lugar.

Se leen en cada llamada (no al importar) para que los tests puedan cambiarlas con monkeypatch.
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VERSION_APP = "1.0.0"
EQUIPO = ["Mariana Marin", "Úrsula Bustamante", "Daniela Garcés", "Cynthia Vaca"]


def _texto(nombre: str, defecto: str) -> str:
    return os.getenv(nombre, defecto)


def _numero(nombre: str, defecto: float) -> float:
    try:
        return float(os.getenv(nombre, defecto))
    except ValueError:
        return defecto


def modelo() -> str:
    return _texto("MODELO_OPENAI", "gpt-4o-mini")


def version_prompt_agente() -> str:
    return _texto("VERSION_PROMPT_AGENTE", "v1")


def version_prompt_vision() -> str:
    return _texto("VERSION_PROMPT_VISION", "v1")


def entorno() -> str:
    return _texto("ENTORNO", "local")


def origenes_permitidos() -> list[str]:
    return [o.strip() for o in _texto("ORIGENES_PERMITIDOS", "*").split(",") if o.strip()]


def pais_por_defecto() -> str:
    return _texto("PAIS_POR_DEFECTO", "OTRO")


def proveedor_por_defecto() -> str:
    return _texto("PROVEEDOR_POR_DEFECTO", "simulado")


def max_imagen_bytes() -> int:
    return int(_numero("MAX_IMAGEN_MB", 5) * 1024 * 1024)


def limite_fotos_dia() -> int:
    return int(_numero("LIMITE_FOTOS_DIA", 20))


def limite_agente_dia() -> int:
    return int(_numero("LIMITE_AGENTE_DIA", 50))


def hay_llave_openai() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def costo_usd(tokens_entrada: int, tokens_salida: int) -> float:
    """Costo estimado de una llamada al modelo, con los precios configurados por millón de tokens."""
    entrada = _numero("PRECIO_ENTRADA_USD_1M", 0.15)
    salida = _numero("PRECIO_SALIDA_USD_1M", 0.60)
    return round(tokens_entrada * entrada / 1_000_000 + tokens_salida * salida / 1_000_000, 6)
