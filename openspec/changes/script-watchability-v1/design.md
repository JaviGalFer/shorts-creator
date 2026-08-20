# Design: script-watchability-v1

Todo el cambio es contrato editorial-en-prompt + tests. Cero cambios de código de
comportamiento: ni rutas de control, ni contratos entre etapas, ni formato de datos.

> **Estado:** COMPLETED / VERIFIED / CLOSED (pending authorized merge). Hardening final de
> hook/cierre (`9fadc10`) y E2E real `cmo-2026-08-20-164453` VALIDATED (VIDEOS_ONLY + Pexels,
> 27.92s in-range, con 2 repairs dentro de budget sin degradar watchability). Suite completa
> `1880 passed, 0 failed`; `git diff --check` limpio. Ver `results.md`.

## Dónde vive cada pieza

| Pieza | Archivo:línea actual |
|-------|----------------------|
| `SYSTEM_PROMPT_V2` (ritmo/narración) | `script/generator.py:71-242` |
| CTA obligatorio (ritmo) | `generator.py:81` |
| CTA en instrucción de duración | `generator.py:448` |
| CTA en instrucción de retry | `generator.py:978` |
| `VOICEOVER_REPAIR_SYSTEM_PROMPT` | `generator.py:280-295` |
| `_build_voiceover_repair_prompt` | `generator.py:1251-1367` |
| `VOICEOVER_COMPRESSION_SYSTEM_PROMPT` | `generator.py:249-277` |

## 1. Contrato editorial en SYSTEM_PROMPT_V2

Se expande la sección "## Reglas de narración (voiceover)" y se refina la regla de hook de
"## Reglas de ritmo". Contenido:

### Hook (escena 1, la primera frase)
- Abrir directamente con el elemento más interesante.
- Razón concreta para seguir viendo pronto: hecho sorprendente concreto, consecuencia
  inesperada, contradicción, mecanismo intrigante o pregunta concreta con contenido.
- Evitar introducciones y clickbait sin payoff; "¿Sabías que...?" nunca como muletilla.
- El vídeo empieza aportando valor desde la primera frase.

### Desarrollo / progresión
- Cada frase aporta información o progresión; preferir mecanismo/causa-efecto/dato/ejemplo/
  contraste sobre adjetivos y énfasis.
- Evitar recapitulaciones, tono escolar, moralejas, transiciones escolares innecesarias.
- Escenas como progresión (hook → contexto mínimo → mecanismo/tensión → consecuencia/payoff
  → cierre), no lista de hechos independientes. `narrativeFunction` puede reflejarlo, sin
  matriz rígida.

### Cierre — CTA NO obligatorio
- El cierre por defecto es el último dato, consecuencia o payoff.
- Evitar "nos enseña que...", "es una lección de...", "así que la próxima vez...",
  "finalmente...", "en conclusión..." y moralejas artificiales.

### Factualidad
- No inventar cifras/fechas/nombres/mecanismos/hechos para hacer el texto más atractivo.
- Sin dato seguro → explicar el mecanismo con precisión.

## 2. Alineación de las superficies de CTA

Las tres superficies dejan de ordenar CTA obligatorio:
- `generator.py:81` → el cierre deja rematar el último dato/payoff; CTA no obligatorio.
- `generator.py:448` → "Si el cierre necesita un remate o CTA, va dentro de la voz en off
  de la última escena, nunca como escena separada; el payoff puede cerrar sin CTA".
- `generator.py:978` → misma lógica en retry.
- No se introduce ningún `ctaMode`/`engagementMode`/`engagementPlacement` (DEFERRED).

## 3. EXPAND (repair)

- `VOICEOVER_REPAIR_SYSTEM_PROMPT` y `_build_voiceover_repair_prompt` añaden, por orden:
  1. causa o mecanismo; 2. detalle concreto relevante; 3. consecuencia; 4. ejemplo útil.
- Prohibido: repetir lo mismo/reformular para ocupar lugar/adjetivos/moralejas/
  introducciones/CTA/ideas ajenas/inventar facts.
- Preservar: fuerza del hook de la escena 1, causalidad, payoff, tono.

## 4. COMPRESS (repair)

- Recortar primero: 1. redundancia; 2. intensificadores; 3. contexto prescindible;
  4. conectores; 5. frases accesorias.
- Preservar prioritariamente: hook, hechos concretos, causa/efecto, mecanismo, payoff, tono.
- No convertir un hook concreto en introducción genérica al comprimir.
- Ya no existe CTA obligatorio que preservar.

## 5. VOICEOVER_COMPRESSION_SYSTEM_PROMPT

Alineación mínima: ampliar la lista de qué conservar en compresión bootstrap con
hook/hechos/causa-efecto/payoff y la regla de no convertir hook en intro genérica.
Se respeta el shape (solo `sceneNumber`+`voiceover`, sin `visualPlan` como campo emitido,
"SOLO JSON", "No devuelvas"), que está cubierto por `test_f9_compression_system_prompt_shape`.

## 6. No tocar

- `evaluate_duration_fitting`, word budgets, ratios, `MAX_DURATION_REPAIRS`,
  `distribute_words`, scene planning, audio/TTS, renderer, visuales.
- No validadores de prosa ni scoring; la mejora es contrato de prompt + evidencia real.

## 7. Invariantes de tests que se respetan al redactar

- Los prompts de repair NO contienen literalmente `minimumWords` / `maximumWords`
  (test_repair_prompt_has_no_bootstrap_budget_contract).
- `VOICEOVER_REPAIR_SYSTEM_PROMPT` conserva `EXPAND`, `COMPRESS`, `"sceneNumber"`,
  `"voiceover"`, `visualPlan` (test_duration_fitting_contract).
- `VOICEOVER_COMPRESSION_SYSTEM_PROMPT` no contiene `assetPreferences` ni `visualSequence`.
- Linea de persona ("Eres un guionista senior...") y ausencia de "histórico" en los 80
  primeros caracteres se preservan (SYSTEM_PROMPT_V2[:80]).

## 8. Test suite nueva

`tests/test_script_watchability.py` cubre: contrato editorial, hook first-sentence,
anti-introducción, anti-clickbait vacío, progresión, anti-moraleja, factualidad,
CTA NO obligatorio y ausencia de "síguenos/like/comenta" obligatorio; consistencia de CTA
en las 3 superficies; políticas EXPAND (mecanismo primero, anti-filler, no moraleja, no
CTA, factualidad, preservación hook/payoff) y COMPRESS (orden de recorte + preservación +
no intro genérica); y contratos (límite global en duration instruction, schema de repair
intacto, visualPlan fuera de repair).

## 9. Validación real (max 2)

- A) "Cómo sobreviven los pingüinos emperador al invierno antártico" — 30s,
  AUTO, providers wikimedia_commons,pixabay,pexels, ElevenLabs.
- B) "Cómo funciona un motor de dos tiempos" — misma configuración.
- Evaluación cualitativa del SCRIPT FINAL (hook inicial/final, desarrollo, cierre, y si
  hubo EXPAND/COMPRESS: comparar antes/después). Sin score numérico artificial.

## 10. Cierre / limitación futura

- Limitación futura explícita: configuración de engagement/CTA (`ctaMode`, `engagementMode`,
  `engagementPlacement`, ej. NONE/FOLLOW/LIKE/COMMENT/INTERACTIVE/AUTO). NO implementar aquí.