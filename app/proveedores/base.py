"""Interfaz común para todos los proveedores de compra (patrón adaptador)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class ProveedorCompra(ABC):
    id: str
    nombre: str
    tipo_integracion: str
    paises: list[str]

    @abstractmethod
    def cotizar(self, faltantes: list[dict], pais: str | None) -> dict:
        """Devuelve el carrito con precios referenciales."""

    @abstractmethod
    def enlace_compra(self, faltantes: list[dict], pais: str | None) -> list[dict] | None:
        """Devuelve enlaces de búsqueda por producto, o None si el proveedor no tiene enlaces."""
