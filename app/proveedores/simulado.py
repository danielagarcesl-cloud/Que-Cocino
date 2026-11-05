"""Proveedor por defecto: precios referenciales locales de data/precios_simulados.json."""
from __future__ import annotations

from app.carrito import armar_carrito
from app.modelos import Catalogo
from app.proveedores.base import ProveedorCompra


class ProveedorSimulado(ProveedorCompra):
    id = "simulado"
    tipo_integracion = "simulado"

    def __init__(self, catalogo: Catalogo):
        self.catalogo = catalogo
        self.nombre = catalogo.proveedores.get("simulado", {}).get("nombre", "Precios referenciales")
        self.paises = list(catalogo.paises)

    def cotizar(self, faltantes: list[dict], pais: str | None) -> dict:
        precios = self.catalogo.precios.get((pais or "").upper())
        return armar_carrito(faltantes, precios, pais, self.catalogo)

    def enlace_compra(self, faltantes: list[dict], pais: str | None) -> None:
        return None
