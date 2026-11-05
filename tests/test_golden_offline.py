from evals.correr_golden import correr


def test_golden_offline_corre_y_puntua():
    res = correr("v1", real=False)
    assert res["total"] >= 5
    fallidos = {f["caso"]["id"]: [n for n, ok, _ in f["checks"] if not ok] for f in res["filas"] if not f["paso"]}
    assert not fallidos, fallidos  # las respuestas grabadas cumplen: así sabemos que los evaluadores funcionan


def test_evaluadores_detectan_fallas():
    import json
    from app.agente import responder
    from app.modelos import catalogo_global
    from evals.correr_golden import CARPETA, ClienteGrabado
    from evals.evaluadores import evaluar
    caso = next(c for c in json.loads((CARPETA / "golden_set.json").read_text("utf-8")) if c["id"] == "G3")
    malo = [{"tool_calls": [["sugerir_menu", {}]]}, {"content": "Haz unos Tacos de frijol y aguacate con tu palta."}]
    r = responder(caso["entrada"]["mensaje"], caso["entrada"]["contexto"], cliente=ClienteGrabado(malo), catalogo=catalogo_global())
    fallidas = [n for n, ok, _ in evaluar(caso, r, catalogo_global()) if not ok]
    assert fallidas == ["palabras_prohibidas"]
