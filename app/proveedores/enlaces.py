"""Proveedores con enlaces de búsqueda públicos (sin scraping ni API privada).

Estas plataformas no ofrecen una API pública para armar carritos. La versión 1 entrega
un enlace de búsqueda por producto y cotiza con los precios referenciales del simulado.
"""
from __future__ import annotations

from urllib.parse import quote

from app.modelos import Catalogo
from app.paises import nombre_local
from app.proveedores.simulado import ProveedorSimulado


class ProveedorEnlace(ProveedorSimulado):
    tipo_integracion = "enlace_busqueda"

    def __init__(self, id: str, config: dict, catalogo: Catalogo):
        super().__init__(catalogo)
        self.id = id
        self.nombre = config.get("nombre", id)
        self.plantillas: dict[str, str] = config.get("plantillas", {})
        self.paises = list(self.plantillas)
        self.verificado = bool(config.get("verificado", False))

    def url_busqueda(self, consulta: str, pais: str | None) -> str | None:
        plantilla = self.plantillas.get((pais or "").upper())
        if not plantilla:
            return None
        return plantilla.replace("{consulta}", quote(consulta, safe=""))

    def enlace_compra(self, faltantes: list[dict], pais: str | None) -> list[dict] | None:
        enlaces = []
        for f in faltantes:
            nombre = nombre_local(f["ingrediente_id"], pais, self.catalogo)
            url = self.url_busqueda(nombre, pais)
            if url:
                enlaces.append({"ingrediente_id": f["ingrediente_id"], "nombre": nombre, "url": url})
        return enlaces or None
