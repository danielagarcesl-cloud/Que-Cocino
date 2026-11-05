import json

import pytest

from app.vision import ErrorTamanoImagen, ErrorTipoImagen, detectar_ingredientes
from tests.conftest import ClienteFalso, respuesta_falsa

SALIDA_MODELO = {"ingredientes": [
    {"nombre": "Papas", "confianza": 0.9}, {"nombre": "aguacate", "confianza": 0.8},
    {"nombre": "cosa rara", "confianza": 0.7}, {"nombre": "huevo", "confianza": 0.3}]}


def test_vision_con_cliente_falso(catalogo):
    cliente = ClienteFalso([respuesta_falsa(json.dumps(SALIDA_MODELO))])
    r = detectar_ingredientes(b"\xff\xd8bytes", "image/jpeg", pais="MX", cliente=cliente, catalogo=catalogo)
    assert r["reconocidos"] == ["papa", "palta"]
    assert r["no_reconocidos"] == ["cosa rara"]
    assert r["dudosos"] == ["huevo"]
    assert r["nombres"]["palta"] == "aguacate"
    req = cliente.requests[0]
    assert req["response_format"]["json_schema"]["strict"] is True
    assert req["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_imagen_grande_rechazada_antes_del_modelo(catalogo):
    cliente = ClienteFalso([])
    with pytest.raises(ErrorTamanoImagen):
        detectar_ingredientes(b"0" * (6 * 1024 * 1024), "image/jpeg", cliente=cliente, catalogo=catalogo)
    assert cliente.requests == []


def test_gif_rechazado_antes_del_modelo(catalogo):
    cliente = ClienteFalso([])
    with pytest.raises(ErrorTipoImagen):
        detectar_ingredientes(b"GIF89a", "image/gif", cliente=cliente, catalogo=catalogo)
    assert cliente.requests == []
