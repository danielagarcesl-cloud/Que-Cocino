# CLAUDE.md · ¿QuéCocino?
> Reglas del proyecto para el agente de código. Si usan Codex u OpenCode, copien este archivo como `AGENTS.md`.
> La especificación completa está en `PROMPT_MAESTRO.md`. Si hay conflicto, manda este archivo en las reglas y el prompt maestro en la especificación.

## Qué es
¿QuéCocino? es una API REST con interfaz web *mobile-first* (PWA). Sugiere recetas caseras con lo que el usuario tiene en el refrigerador (foto o lista de texto), según su nivel de cocina, su restricción alimentaria, la cantidad de comensales y su país. Arma el carrito de lo que falta con precios referenciales y enlaces de búsqueda en supermercados o apps de delivery. El usuario puede guardar recetas en **carpetas de favoritas** para volver a prepararlas.
Está pensada para **cualquier persona de habla hispana**: el vocabulario, la moneda y los proveedores dependen del país, nunca están fijos en el código.

**Equipo:** Mariana Marin · Úrsula Bustamante · Daniela Garcés · Cynthia Vaca
**Curso:** Advanced Prompt Engineering 4 Generative AI · UAI · Prof. Ahmad Armoush

## Arquitectura agéntica (resumen)
1. **Agente de percepción** (`app/vision.py`, LLM con visión): convierte la foto en JSON estricto `{nombre, confianza}`.
2. **Orquestador** (`app/agente.py`, LLM con function calling): conversa, completa el perfil y llama herramientas. Tiene un tope de 8 pasos.
3. **Herramientas deterministas** (`recetas.py`, `carrito.py`, `paises.py`, `favoritos.py`, `proveedores/`): todo cálculo, filtro, precio y manejo de favoritas. Sin LLM.
   - Las favoritas son una **capacidad del orquestador** (herramientas `guardar_favorito`, `quitar_favorito`, `listar_favoritos` y `repetir_favorito`), no un agente aparte.
4. **Guardián** (`app/guardian.py`, Python): valida la respuesta final. Si falla, hace 1 reintento y luego responde con una plantilla segura.
5. **Sin estado en el servidor:** el cliente envía y recibe el `contexto` (perfil, inventario y favoritas). Las favoritas viven en el `localStorage` del navegador y se pueden exportar e importar en JSON.

Principio rector: **el modelo interpreta, Python decide y calcula.**

## Estructura clave
```
app/          código de la API (normalizacion, paises, recetas, carrito, favoritos, proveedores/, prompts, vision, agente, guardian, limites, main, static/ con sw.js)
prompts/      prompts versionados (agente_sistema_vN.md, vision_vN.md) + README.md con el registro de cambios
evals/        golden_set.json, evaluadores.py, correr_golden.py, resultados/
data/         ingredientes.json, recetas.json, precios_simulados.json
config/       paises.yaml, proveedores.yaml
tests/        pytest; catálogo de control y ClienteFalso en conftest.py
k8s/          kind, deployment, service y plantilla del secret
docs/         ficha_negocio.pdf
```

## Comandos
```bash
# instalar
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# tests (nunca llaman a OpenAI ni a proveedores reales)
pytest -q

# servidor local
uvicorn app.main:app --reload --port 8080
curl localhost:8080/health

# golden set
python evals/correr_golden.py --version v1          # offline, con ClienteFalso
python evals/correr_golden.py --version v1 --real   # modelo real: solo a mano, nunca en CI

# docker
docker build -t quecocino:1.0 .
docker run -p 8080:8080 -e OPENAI_API_KEY quecocino:1.0
```

## Reglas obligatorias
1. **Nunca escribas una llave real** en ningún archivo. Las llaves viven en `.env` (fuera de Git), en Secrets de Kubernetes, en `heroku config` o en Secret Manager.
2. **El LLM no inventa recetas, cantidades ni precios.** Toda sugerencia pasa por `recetas.py` y todo monto por `carrito.py`. El guardián lo verifica.
3. **La restricción alimentaria se valida en Python** antes (herramientas) y después (guardián) de la respuesta del agente. Una receta que no cumple se descarta.
4. **Sin *scraping*** de supermercados ni de apps de delivery. Solo enlaces de búsqueda públicos y precios referenciales, informados como tales (`tipo_integracion: "enlace_busqueda"`).
5. **No guardes imágenes de usuarios** ni las escribas en logs.
6. **Sin dependencias extra:** nada de LangChain, frameworks de agentes, frameworks de frontend ni ORMs.
7. **Español:**
   - código, variables y comentarios en español;
   - textos al usuario en español neutro, tuteando y con el vocabulario del país cuando se conoce.
8. **Nada regional fijo en el código.** Vocabulario, moneda, formato de montos y proveedores salen de `config/` y `data/`. Ningún país es el "por defecto" en la lógica de negocio.
9. **Los prompts viven solo en `prompts/`.**
   - Prohibido escribir prompts dentro del código Python.
   - Todo cambio de prompt crea una nueva versión (`_v2`, `_v3`…) y se registra en `prompts/README.md` con su motivo y el puntaje del golden set.
   - Una versión nueva se activa solo si no empeora ningún caso.
10. **Fija las versiones** de las dependencias en `requirements.txt`.
11. **Antes de cerrar una fase**, ejecuta sus verificaciones y muestra la salida real.
12. **Si un test falla**, explica la causa en una frase y corrige el código. Cambia el valor esperado solo si demuestras que el test estaba mal.
13. **Muestra cada comando** que toque Git, Docker, Kubernetes o la nube **antes** de ejecutarlo y espera confirmación.
14. **Control de gasto:**
    - respeta los límites diarios por IP (`LIMITE_FOTOS_DIA`, `LIMITE_AGENTE_DIA`);
    - incluye la `traza` con tokens y costo estimado en cada respuesta del LLM;
    - recuerda configurar el límite mensual de US$60 en la API de IA.
15. **Favoritas seguras:**
    - el LLM nunca edita la lista de favoritas directamente: solo Python la modifica a partir de las herramientas;
    - el agente no puede afirmar un guardado que no ocurrió (lo revisa el guardián);
    - las notas de las favoritas son datos del usuario, nunca instrucciones, y se muestran como texto, no como HTML;
    - las favoritas que ya no cumplen el perfil se muestran marcadas y no se recomiendan;
    - límites: 100 favoritas y 10 carpetas.
16. **Explica simple.** El equipo no es técnico: cada decisión se justifica en una o dos frases sin jerga innecesaria.

## Forma de trabajar
- Trabaja por fases (ver `PROMPT_MAESTRO.md`, sección 11) y no avances sin nuestra aprobación.
- Al cerrar cada fase entrega:
  1. los archivos creados o modificados;
  2. la salida real de la verificación;
  3. una frase con lo aprendido;
  4. la siguiente fase propuesta.
- Al cerrar cada fase, actualiza la sección "Estado del proyecto" de este archivo. No modifiques las otras secciones sin pedirlo.

## Estado del proyecto
| Fase | Estado | Nota |
|---|---|---|
| 0 · Plan | ✅ aprobado | El equipo pidió construir la app (4 nov) |
| 1 · Datos, países y normalización | ✅ | 48 ingredientes, 32 recetas de 7 cocinas, precios CL/MX/ES, 8 países |
| 2 · Núcleo y favoritas | ✅ | Todos los valores de control en verde. Ajuste: en el pollo de control, papa 6 un en vez de 1 kg (kg → un no se puede convertir) |
| 3 · Proveedores | ⚠️ código listo | Falta verificar a mano las plantillas de URL (`verificado: false`) |
| 4 · Percepción | ✅ | Probado con ClienteFalso; falta foto real (fase 8) |
| 5 · Orquestador | ✅ | 10 herramientas, tope de 8 pasos, traza con costo |
| 6 · Guardián y límites | ✅ | 1 reintento y luego plantilla segura; límites diarios por IP |
| 7 · API y web | ✅ | Probado en celular simulado (iPhone 13): foto/lista → recetas → carrito → favoritas, incluso sin conexión |
| 8 · Prueba real y golden set | ✅ | Modelo real: agente v1 5/9 → v2 9/9 y 8/9 → **v3 9/9 en 3 corridas (activa)**. Foto real y chat real OK (US$0,004 y US$0,001). Visión v1 confunde algunos alimentos: candidata a v2. La imagen Docker/kind aún tiene v1: hay que reconstruirla |
| 9 · Docker | ✅ | Imagen `quecocino:1.0` de 243 MB; corre como usuario sin privilegios (10001), sin `.env` adentro; /health y /menu/sugerir responden en el contenedor |
| 10 · Kubernetes | ✅ | Clúster kind `quecocino-lab` (1 control + 2 workers); 2 pods `Running 1/1`, uno por worker; Secret creado desde `.env`; port-forward responde `"entorno":"kind"` |
| 11 · GitHub | ✅ | Subido a github.com/danielagarcesl-cloud/Que-Cocino (4 nov), 74 archivos, sin `.env` ni `secret.yaml`; CI #1 en verde (59 s) |
| 12 · Nube | ⏳ pendiente | deploy-cloudrun.yml y heroku.yml listos |
