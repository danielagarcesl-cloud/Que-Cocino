# Prompts versionados de ¿QuéCocino?

Los prompts viven solo en esta carpeta; el código los carga con `app/prompts.py`.
La versión activa se elige con las variables `VERSION_PROMPT_AGENTE` y `VERSION_PROMPT_VISION`.
Una versión nueva se activa solo si en el golden set (`evals/`) mejora o empata sin empeorar ningún caso.

| Prompt | Versión | Fecha | Cambio | Motivo | Golden set (modelo real) |
|---|---|---|---|---|---|
| agente_sistema | v1 | 2026-11-04 | Versión inicial (copiada del prompt maestro, sección 6.9) | — | pendiente (fase 8, requiere OPENAI_API_KEY) |
| vision | v1 | 2026-11-04 | Versión inicial | — | se evalúa con fotos reales en la fase 8 |
| guardian_correccion | v1 | 2026-11-04 | Mensaje de corrección que el guardián envía al modelo cuando una respuesta falla | — | cubierto por tests |

## Cómo crear la v2 (fase 8)
1. `python evals/correr_golden.py --version v1 --real` y revisar `evals/resultados/v1.md`.
2. Anotar qué casos fallan y por qué.
3. Copiar `agente_sistema_v1.md` a `agente_sistema_v2.md` y hacer cambios mínimos y justificados.
4. `python evals/correr_golden.py --version v2 --real` y completar la tabla de arriba.
5. Si v2 no empeora ningún caso, activar con `VERSION_PROMPT_AGENTE=v2`.
