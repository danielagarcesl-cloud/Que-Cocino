"""Corre el golden set para una versión del prompt del orquestador.

    python evals/correr_golden.py --version v1          # offline: respuestas grabadas, sin costo
    python evals/correr_golden.py --version v1 --real   # modelo real: requiere OPENAI_API_KEY (solo a mano, nunca en CI)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app import agente  # noqa: E402
from app.modelos import catalogo_global  # noqa: E402
from evals.evaluadores import evaluar  # noqa: E402

CARPETA = RAIZ / "evals"


class ClienteGrabado:
    """Imita la forma de las respuestas de OpenAI con pasos grabados."""

    def __init__(self, pasos):
        self.pasos = list(pasos)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))

    def _crear(self, **_):
        paso = self.pasos.pop(0) if self.pasos else {"content": "Sin respuesta grabada."}
        llamadas = None
        if "tool_calls" in paso:
            llamadas = [SimpleNamespace(id=f"g{i}", type="function", function=SimpleNamespace(
                name=n, arguments=json.dumps(a, ensure_ascii=False))) for i, (n, a) in enumerate(paso["tool_calls"])]
        msg = SimpleNamespace(content=paso.get("content"), tool_calls=llamadas)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)],
                               usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0))


def correr(version: str, real: bool) -> dict:
    os.environ["VERSION_PROMPT_AGENTE"] = version
    casos = json.loads((CARPETA / "golden_set.json").read_text("utf-8"))
    grabadas = json.loads((CARPETA / "respuestas_grabadas.json").read_text("utf-8"))
    catalogo = catalogo_global()
    filas, aprobados, costo = [], 0, 0.0
    for caso in casos:
        cliente = agente.crear_cliente() if real else ClienteGrabado(grabadas.get(caso["id"], []))
        r = agente.responder(caso["entrada"]["mensaje"], caso["entrada"]["contexto"], cliente=cliente, catalogo=catalogo)
        checks = evaluar(caso, r, catalogo)
        paso = all(ok for _, ok, _ in checks)
        aprobados += paso
        costo += r["traza"]["costo_estimado_usd"]
        filas.append({"caso": caso, "respuesta": r, "checks": checks, "paso": paso})
    return {"version": version, "real": real, "aprobados": aprobados, "total": len(casos), "costo": costo, "filas": filas}


def escribir_informe(res: dict) -> Path:
    modo = "modelo real" if res["real"] else "offline (respuestas grabadas)"
    lineas = [f"# Golden set · prompt {res['version']} · {modo}", "",
              f"Fecha: {datetime.now():%Y-%m-%d %H:%M} · Resultado: **{res['aprobados']}/{res['total']}** · "
              f"Costo estimado: US${res['costo']:.4f}", "",
              "| Caso | Descripción | Resultado | Verificaciones fallidas | Herramientas |", "|---|---|---|---|---|"]
    for f in res["filas"]:
        fallidas = "; ".join(f"{n} ({d})" if d else n for n, ok, d in f["checks"] if not ok) or "—"
        lineas.append(f"| {f['caso']['id']} | {f['caso']['descripcion']} | {'✅' if f['paso'] else '❌'} | {fallidas} | "
                      f"{', '.join(f['respuesta']['herramientas_usadas']) or '—'} |")
    lineas += ["", "## Respuestas", ""]
    for f in res["filas"]:
        lineas += [f"**{f['caso']['id']}** · {f['caso']['entrada']['mensaje']}", "", "> " + f["respuesta"]["respuesta"].replace("\n", "\n> "), ""]
    sufijo = "" if res["real"] else "_offline"
    ruta = CARPETA / "resultados" / f"{res['version']}{sufijo}.md"
    ruta.parent.mkdir(exist_ok=True)
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return ruta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", default="v1")
    p.add_argument("--real", action="store_true", help="usa el modelo real (requiere OPENAI_API_KEY)")
    a = p.parse_args()
    if a.real and not os.getenv("OPENAI_API_KEY"):
        sys.exit("Falta OPENAI_API_KEY. Para probar sin costo, corre sin --real.")
    res = correr(a.version, a.real)
    ruta = escribir_informe(res)
    print(f"Prompt {a.version}: {res['aprobados']}/{res['total']} casos aprobados · informe en {ruta.relative_to(RAIZ)}")
    for f in res["filas"]:
        if not f["paso"]:
            print(f"  ❌ {f['caso']['id']}: " + "; ".join(n for n, ok, _ in f["checks"] if not ok))


if __name__ == "__main__":
    main()
