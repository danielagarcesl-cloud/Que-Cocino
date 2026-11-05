from app.agente import Estado, ejecutar_herramienta
from app.guardian import validar_respuesta
from app.modelos import Perfil

VEGETARIANO = Perfil(nivel="avanzado", restriccion="vegetariano", pais="CL", porciones=4,
                     inventario=["papa", "huevo", "cebolla", "queso"])


def _estado(catalogo, perfil=VEGETARIANO, favoritos=None):
    return Estado(perfil=perfil, favoritos=favoritos or [], catalogo=catalogo)


def test_receta_incompatible_falla(catalogo):
    e = _estado(catalogo, perfil=Perfil(nivel="avanzado", restriccion="ninguna"))
    ejecutar_herramienta("sugerir_menu", {}, e)  # devuelve tortilla, budín y pollo
    r = validar_respuesta("Prepara el Pollo al horno con papas.", e.resultados, VEGETARIANO, catalogo)
    assert not r["ok"]


def test_receta_no_devuelta_falla(catalogo):
    r = validar_respuesta("Te recomiendo la Tortilla de papas.", [], VEGETARIANO, catalogo)
    assert not r["ok"]


def test_monto_inventado_falla(catalogo):
    e = _estado(catalogo)
    ejecutar_herramienta("armar_carrito", {"receta_id": "tortilla"}, e)
    assert validar_respuesta("Te falta aceite: $3.490 (precios referenciales).", e.resultados, VEGETARIANO, catalogo)["ok"]
    assert not validar_respuesta("Te falta aceite: $9.999 (precios referenciales).", e.resultados, VEGETARIANO, catalogo)["ok"]


def test_falta_aviso_referencial(catalogo):
    e = _estado(catalogo)
    ejecutar_herramienta("armar_carrito", {"receta_id": "tortilla"}, e)
    assert not validar_respuesta("El carrito suma $3.490.", e.resultados, VEGETARIANO, catalogo)["ok"]


def test_guardado_no_confirmado_falla(catalogo):
    r = validar_respuesta("Listo, la guardé en tus favoritas.", [], VEGETARIANO, catalogo)
    assert not r["ok"]
    assert validar_respuesta("Si quieres, puedes guardarla en tus favoritas.", [], VEGETARIANO, catalogo)["ok"]


def test_favorita_incompatible_con_advertencia(catalogo):
    e = _estado(catalogo, favoritos=[{"receta_id": "pollo"}])
    ejecutar_herramienta("listar_favoritos", {}, e)
    texto = "Tu favorita Pollo al horno con papas ya no cumple tu restricción vegetariana, así que no te la recomiendo."
    r = validar_respuesta(texto, e.resultados, VEGETARIANO, catalogo)
    assert r["ok"] and r["recetas_sugeridas"] == []
