# Prompts versionados de ¿QuéCocino?

Los prompts viven solo en esta carpeta; el código los carga con `app/prompts.py`.
La versión activa se elige con las variables `VERSION_PROMPT_AGENTE` y `VERSION_PROMPT_VISION`.
Una versión nueva se activa solo si en el golden set (`evals/`) mejora o empata sin empeorar ningún caso.

| Prompt | Versión | Fecha | Cambio | Motivo | Golden set (modelo real) |
|---|---|---|---|---|---|
| agente_sistema | v1 | 2026-11-04 | Versión inicial (copiada del prompt maestro, sección 6.9) | — | **5/9** (falla G2, G6, G7, G9; G3 aprueba pero inventa "tacos veganos") |
| agente_sistema | v2 | 2026-11-05 | 6 cambios mínimos: no proponer preparaciones propias; usar sugerir_menu sin pedir cantidades; pregunta directa con ¿?; etiquetas ante alergia aunque falten datos; listar_favoritos primero; decir "no cumple" | Corregir los 4 fallos de v1 y el invento de G3 | **9/9** y **8/9** (G7 inestable: a veces usa calcular_faltantes en vez de listar_favoritos) |
| agente_sistema | **v3 ✅ activa** | 2026-11-05 | Igual a v2, pero la regla de favoritas explica por qué usar listar_favoritos aunque la lista esté en el contexto, y prohíbe reemplazarla por calcular_faltantes | Estabilizar G7 | **9/9 en 3 corridas seguidas**; no empeora ningún caso respecto a v1 ni v2 |
| vision | v1 | 2026-11-04 | Versión inicial | — | Foto real de un refri (2026-11-05): reconoció plátano y arroz (correctos); confundió vienesas con zanahoria y marcó limón y tomate como seguros aunque estaban borrosos en el cajón. Costo US$0,0039. Candidata a v2 |
| guardian_correccion | v1 | 2026-11-04 | Mensaje de corrección que el guardián envía al modelo cuando una respuesta falla | — | cubierto por tests |

## Comparación del agente (modelo gpt-4o-mini, 2026-11-05)
| Caso | v1 | v2 (corrida 1 / 2) | v3 (corridas 1 / 2 / 3) |
|---|---|---|---|
| G1 · Chile vegetariano, prioriza tortilla | ✅ | ✅ / ✅ | ✅ / ✅ / ✅ |
| G2 · Sin perfil, debe preguntar | ❌ | ✅ / ✅ | ✅ / ✅ / ✅ |
| G3 · México vegano | ✅ (pero inventa receta) | ✅ / ✅ | ✅ / ✅ / ✅ |
| G4 · España sin gluten, 2 comensales | ✅ | ✅ / ✅ | ✅ / ✅ / ✅ |
| G5 · Intento de inyección | ✅ | ✅ / ✅ | ✅ / ✅ / ✅ |
| G6 · Alergia, revisar etiquetas | ❌ | ✅ / ✅ | ✅ / ✅ / ✅ |
| G7 · Favoritas para hoy | ❌ | ✅ / ❌ | ✅ / ✅ / ✅ |
| G8 · Guardar en carpeta | ✅ | ✅ / ✅ | ✅ / ✅ / ✅ |
| G9 · Favorita que ya no cumple | ❌ | ✅ / ✅ | ✅ / ✅ / ✅ |
| **Total** | **5/9** | **9/9 · 8/9** | **9/9 · 9/9 · 9/9** |

Costo de cada corrida completa: ~US$0,005. Informes en `evals/resultados/`.
Aprendizaje: la IA no responde siempre igual; una versión se da por buena solo si pasa varias corridas seguidas.

## Cómo crear la v2 (fase 8)
1. `python evals/correr_golden.py --version v1 --real` y revisar `evals/resultados/v1.md`.
2. Anotar qué casos fallan y por qué.
3. Copiar `agente_sistema_v1.md` a `agente_sistema_v2.md` y hacer cambios mínimos y justificados.
4. `python evals/correr_golden.py --version v2 --real` y completar la tabla de arriba.
5. Si v2 no empeora ningún caso, activar con `VERSION_PROMPT_AGENTE=v2`.
