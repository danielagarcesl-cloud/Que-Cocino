import json

import pytest
from fastapi.testclient import TestClient

from app.limites import limitador
from app.main import app
from tests.conftest import ClienteFalso, respuesta_falsa

cliente_http = TestClient(app)
INV = ["papa", "huevo", "cebolla", "queso"]


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    limitador.reiniciar()
    app.state.cliente_openai = None
    yield
    app.state.cliente_openai = None


def test_health():
    r = cliente_http.get("/health").json()
    assert r["status"] == "ok" and r["version_prompt"] == "v3" and "Mariana Marin" in r["equipo"]


def test_opciones():
    r = cliente_http.get("/opciones").json()
    assert "vegano" in r["restricciones"] and {p["codigo"] for p in r["paises"]} >= {"CL", "MX", "ES", "OTRO"}


def test_menu_vegetariano_avanzado():
    r = cliente_http.post("/menu/sugerir", json={"inventario": INV, "nivel": "avanzado", "restriccion": "vegetariano",
                                                 "porciones": 4, "pais": "CL"})
    assert r.status_code == 200
    recetas = r.json()["recetas"]
    assert recetas[0]["receta_id"] == "tortilla_de_papas"
    assert all(x["receta_id"] not in {"pollo_al_horno_con_papas", "charquican"} for x in recetas)


def test_menu_nivel_invalido():
    assert cliente_http.post("/menu/sugerir", json={"inventario": INV, "nivel": "experto", "restriccion": "ninguna"}).status_code == 422


def test_carrito_cl_y_es():
    base = {"receta_id": "tortilla_de_papas", "inventario": INV, "porciones": 4}
    cl = cliente_http.post("/carrito", json={**base, "pais": "CL"}).json()
    es = cliente_http.post("/carrito", json={**base, "pais": "ES"}).json()
    assert cl["total_formateado"] == "$3.490" and cl["aviso"] == "Precios referenciales"
    assert es["total_formateado"] == "3,49 €"


def test_carrito_receta_inexistente():
    assert cliente_http.post("/carrito", json={"receta_id": "sushi", "pais": "CL"}).status_code == 404


def test_nombres_locales_por_pais():
    cl = cliente_http.get("/recetas/guacamole?pais=CL").json()
    mx = cliente_http.get("/recetas/guacamole?pais=MX").json()
    assert cl["ingredientes"][0]["nombre"] == "palta" and mx["ingredientes"][0]["nombre"] == "aguacate"


def test_favoritos_endpoints():
    r = cliente_http.post("/favoritos/guardar", json={"favoritos": [], "receta_id": "tortilla_de_papas", "porciones": 2})
    favs = r.json()["favoritos"]
    assert len(favs) == 1
    assert cliente_http.post("/favoritos/guardar", json={"favoritos": [], "receta_id": "sushi"}).status_code == 404
    cien = [{"receta_id": "guacamole", "carpeta": f"C{i % 10}"} for i in range(100)]
    assert cliente_http.post("/favoritos/guardar", json={"favoritos": cien, "receta_id": "gazpacho", "carpeta": "C1"}).status_code == 422
    rep = cliente_http.post("/favoritos/repetir", json={"favoritos": favs, "receta_id": "tortilla_de_papas",
                                                        "inventario": INV, "pais": "CL"}).json()
    assert rep["carrito"]["total_formateado"] == "$3.490" and rep["favoritos"][0]["veces_preparada"] == 1
    lst = cliente_http.post("/favoritos/listar", json={"favoritos": favs + [{"receta_id": "borrada"}],
                                                       "perfil": {"restriccion": "vegano"}}).json()
    assert lst["descartados"] == ["borrada"] and lst["favoritas"][0]["compatible_con_perfil"] is False


def test_detectar_sin_llave_503():
    r = cliente_http.post("/ingredientes/detectar", files={"imagen": ("f.jpg", b"\xff\xd8x", "image/jpeg")})
    assert r.status_code == 503


def test_detectar_tipo_y_tamano():
    assert cliente_http.post("/ingredientes/detectar", files={"imagen": ("f.gif", b"GIF89a", "image/gif")}).status_code == 415
    grande = b"0" * (6 * 1024 * 1024)
    assert cliente_http.post("/ingredientes/detectar", files={"imagen": ("f.jpg", grande, "image/jpeg")}).status_code == 413


def test_limite_de_fotos(monkeypatch):
    monkeypatch.setenv("LIMITE_FOTOS_DIA", "2")
    salida = json.dumps({"ingredientes": [{"nombre": "papa", "confianza": 0.9}]})
    app.state.cliente_openai = ClienteFalso([respuesta_falsa(salida) for _ in range(3)])
    codigos = [cliente_http.post("/ingredientes/detectar", files={"imagen": ("f.jpg", b"\xff\xd8x", "image/jpeg")}).status_code
               for _ in range(3)]
    assert codigos == [200, 200, 429]


def test_agente_sin_llave_503():
    assert cliente_http.post("/agente", json={"mensaje": "hola"}).status_code == 503


def test_agente_con_cliente_falso():
    app.state.cliente_openai = ClienteFalso([
        respuesta_falsa(tool_calls=[("sugerir_menu", {"inventario": INV, "nivel": "principiante", "restriccion": "ninguna"})]),
        respuesta_falsa("Te propongo la Tortilla de papas: solo te falta aceite."),
    ])
    r = cliente_http.post("/agente", json={"mensaje": "¿qué cocino?", "contexto": {"perfil": {"pais": "CL"}}}).json()
    assert r["herramientas_usadas"] == ["sugerir_menu"] and r["traza"]["guardian"] == "ok"


def test_portada_y_sw():
    assert "¿QuéCocino?" in cliente_http.get("/").text
    assert cliente_http.get("/sw.js").status_code == 200


class _ClienteSinSaldo:
    """Imita a OpenAI cuando la cuenta se quedó sin crédito (error 429 insufficient_quota)."""
    def __init__(self):
        import httpx
        import openai

        def crear(**_):
            respuesta = httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))
            raise openai.RateLimitError("You have no credits remaining.", response=respuesta,
                                        body={"code": "credit_balance_exhausted", "type": "insufficient_quota"})

        self.chat = type("Chat", (), {"completions": type("C", (), {"create": staticmethod(crear)})()})()


def test_sin_saldo_en_ia_da_mensaje_claro():
    app.state.cliente_openai = _ClienteSinSaldo()
    r_chat = cliente_http.post("/agente", json={"mensaje": "hola"})
    r_foto = cliente_http.post("/ingredientes/detectar", files={"imagen": ("f.jpg", b"\xff\xd8x", "image/jpeg")})
    for r in (r_chat, r_foto):
        assert r.status_code == 503
        assert "no tiene saldo" in r.json()["detail"]
