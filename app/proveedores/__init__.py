"""Registro de proveedores de compra por país."""
from __future__ import annotations

from app.carrito import recalcular_carrito
from app.modelos import Catalogo
from app.paises import proveedores_de, validar_pais
from app.proveedores.base import ProveedorCompra
from app.proveedores.enlaces import ProveedorEnlace
from app.proveedores.simulado import ProveedorSimulado


def obtener_proveedor(proveedor_id: str | None, pais: str | None, catalogo: Catalogo) -> ProveedorCompra:
    pais = validar_pais(pais, catalogo)
    proveedor_id = proveedor_id or "simulado"
    if proveedor_id not in proveedores_de(pais, catalogo):
        raise ValueError(f"El proveedor {proveedor_id} no está disponible en {pais}. "
                         f"Opciones: {', '.join(proveedores_de(pais, catalogo))}")
    if proveedor_id == "simulado":
        return ProveedorSimulado(catalogo)
    config = catalogo.proveedores.get(proveedor_id)
    if not config:
        raise ValueError(f"Proveedor desconocido: {proveedor_id}")
    return ProveedorEnlace(proveedor_id, config, catalogo)


def proveedores_disponibles(pais: str | None, catalogo: Catalogo) -> list[dict]:
    salida = []
    for pid in proveedores_de(pais, catalogo):
        conf = catalogo.proveedores.get(pid, {})
        salida.append({"id": pid, "nombre": conf.get("nombre", pid),
                       "tipo_integracion": conf.get("tipo_integracion", "simulado"),
                       "verificado": conf.get("verificado", pid == "simulado")})
    return salida


def cotizar_carrito_editable(entradas: list[dict], pais: str | None, proveedor_id: str | None, catalogo: Catalogo) -> dict:
    """"Mi carrito": recalcula precios y arma el enlace de cada producto con el nombre que eligió el usuario."""
    proveedor = obtener_proveedor(proveedor_id, pais, catalogo)
    carrito = recalcular_carrito(entradas, catalogo.precios.get((pais or "").upper()), pais, catalogo)
    url_busqueda = getattr(proveedor, "url_busqueda", None)
    for item in carrito["items"]:
        item["url"] = url_busqueda(item["nombre"], pais) if url_busqueda else None
    carrito.update({
        "proveedor": proveedor.id,
        "proveedor_nombre": proveedor.nombre,
        "tipo_integracion": proveedor.tipo_integracion,
    })
    if any(i["personalizado"] and i["con_precio"] for i in carrito["items"]):
        carrito["aviso_variantes"] = ("En los productos que cambiaste, el precio referencial es el del "
                                      "ingrediente original; el precio real lo ves en la tienda.")
    if proveedor.tipo_integracion == "enlace_busqueda":
        carrito["aviso_enlaces"] = "Los enlaces abren una búsqueda en el proveedor y los precios pueden variar."
    return carrito


def cotizar_compra(faltantes: list[dict], pais: str | None, proveedor_id: str | None, catalogo: Catalogo) -> dict:
    """Carrito + enlaces + aviso de honestidad sobre el tipo de integración."""
    proveedor = obtener_proveedor(proveedor_id, pais, catalogo)
    carrito = proveedor.cotizar(faltantes, pais)
    enlaces = proveedor.enlace_compra(faltantes, pais) or []
    # Cada producto del carrito lleva su propio enlace de búsqueda en la tienda elegida.
    url_por_ingrediente = {e["ingrediente_id"]: e["url"] for e in enlaces}
    for item in carrito["items"]:
        item["url"] = url_por_ingrediente.get(item["ingrediente_id"])
    carrito.update({
        "proveedor": proveedor.id,
        "proveedor_nombre": proveedor.nombre,
        "tipo_integracion": proveedor.tipo_integracion,
        "enlaces": enlaces,
    })
    if proveedor.tipo_integracion == "enlace_busqueda":
        carrito["aviso_enlaces"] = "Los enlaces abren una búsqueda en el proveedor y los precios pueden variar."
        carrito["enlaces_verificados"] = getattr(proveedor, "verificado", False)
    return carrito
