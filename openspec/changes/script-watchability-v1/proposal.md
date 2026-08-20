# Propuesta: script-watchability-v1

**Clasificación AGENTS.md: Level 1** — cambio acotado DENTRO de una parte existente
(prompts del dominio `script/generator.py`). No altera arquitectura, contratos entre
etapas, persistencia, formato de datos, integración externa ni componentes distintos.
OpenSpec se crea por decisión de sesión para dejar decisión editorial útil; no exige
session requerida (solo Level 2 la exigiría).

**Estado: COMPLETED / VERIFIED / CLOSED (pending authorized merge).**

## Contexto

Los vídeos funcionan, pero algunos guiones suenan genéricos/escolares: moralejas
artificiales, cierres tipo "así que la próxima vez...", frases vagas de admiración,
conectores mecánicos ("finalmente", "en conclusión"), relleno para alcanzar duración
y poca densidad de datos/mecanismos. La prioridad especial es la PRIMERA FRASE (hook
real que escucha el espectador = voiceover de la escena 1).

Hallazgo clave del Plan (auditado en código):
- El `SYSTEM_PROMPT_V2` (generator.py:71-242) tiene reglas de ritmo/narración mínimas
  y no incluye ningún contrato editorial de watchability ni guía de progresión.
- Los prompts de duration repair (`VOICEOVER_REPAIR_SYSTEM_PROMPT`, generator.py:280-295,
  y `_build_voiceover_repair_prompt`, generator.py:1251-1367) son direccionales pero
  abiertos: *"Para EXPAND puedes añadir detalle relevante"* — es la puerta al relleno,
  adjetivos, moralejas y datos inventados al estirar hacia la duración objetivo.
- El CTA de seguimiento se ordena como obligatorio en tres superficies (SYSTEM_PROMPT_V2,
  `_build_duration_prompt_instruction_v2` y `_build_retry_instruction_v2`).

## Objetivo

Mejorar de forma perceptible la calidad narrativa del guion, con prioridad en los
primeros segundos, SIN nuevas llamadas LLM, schemas, judges ni lógica compleja. El
cambio debe aprovechar únicamente las llamadas LLM que ya existen (generación inicial +
retry + duration repair EXPAND/COMPRESS).

## Principios del contrato editorial

- Cada frase aporta información o progresión.
- Preferir mecanismo, causa/efecto, dato, ejemplo o contraste; evitar adjetivos y énfasis
  sin información, recapitulaciones, tono escolar y moralejas artificiales.
- Factualidad > espectacularidad: no inventar datos; si no hay dato seguro, explicar el
  mecanismo con precisión.
- No crear una matriz narrativa rígida. Orientación flexible:
  `hook → contexto mínimo → mecanismo/tensión → consecuencia/payoff → cierre`.
- `narrativeFunction` puede apoyar la progresión, pero no se añaden validadores ni schema.

## Hook (máxima prioridad)

- El voiceover de la escena 1 es el hook real. Debe abrir directamente con el elemento
  más interesante. La primera frase debe contener pronto una razón concreta para seguir.
- Preferir: hecho sorprendente concreto, consecuencia inesperada, contradicción,
  mecanismo intrigante, pregunta concreta con contenido.
- Evitar introducciones ("Hoy vamos a hablar de...", "En este vídeo veremos...", "Te voy
  a contar...", "Prepárate para...", "Seguro que alguna vez...") y clickbait sin payoff
  ("Lo que ocurre después te sorprenderá...", "Pero primero...").
- "¿Sabías que...?" no está prohibido, pero nunca como muletilla vacía.

## Campo `hook` top-level

No se crea lógica nueva. El source of truth perceptivo es la escena 1 `voiceover`; el
campo `hook` puede reflejar la idea de apertura sin obligar a hooks distintos. Sin cambio
de schema.

## Cierre — CTA NO obligatorio (cambio de comportamiento)

Se ELIMINA la obligación de incluir un CTA de seguimiento. El cierre por defecto es el
último dato, consecuencia o payoff natural. Se retira/alinea toda instrucción obligatoria
de CTA en SYSTEM_PROMPT_V2, duration instruction y retry instruction, sin dejar
contradicciones. Definido y DEFERRED a futuro: `ctaMode`/`engagementMode`/`engagementPlacement`
y cualquier schema/config equivalente (engagement configurable). Fuera de alcance aquí.

## Alcance (una slice funcional)

1. Contrato editorial watchability en `SYSTEM_PROMPT_V2` (hook + desarrollo + progresión +
   cierre + factualidad) y alineación de las tres supervivientes de instrucción de CTA.
2. Política EXPAND en `VOICEOVER_REPAIR_SYSTEM_PROMPT` + `_build_voiceover_repair_prompt`
   (añadir por orden: causa/mecanismo → detalle relevante → consecuencia → ejemplo; prohibir
   relleno/adjetivos/moralejas/introducciones/CTA/ideas ajenas/datos inventados; preservar
   hook/causalidad/payoff/tono).
3. Política COMPRESS (recortar primero: redundancia → intensificadores → contexto
   prescindible → conectores → frases accesorias; preservar hook/hechos/causa/efecto/
   mecanismo/payoff/tono; no convertir hook en introducción genérica).
4. Alineación de `VOICEOVER_COMPRESSION_SYSTEM_PROMPT` con la política de preservación.
5. Tests offline `tests/test_script_watchability.py`.
6. 1-2 ejecuciones reales de validación (max 2).

## Fuera de alcance

- Engagement/CTA configurable (`ctaMode`, `engagementMode`, `engagementPlacement`...).
- Nuevos schemas, campos o validadores (ni para `narrativeFunction`).
- Nuevas llamadas LLM / critique / rewrite / judge.
- Routing visual, providers, `mediaPreference`, AUTO/MIXED/IMAGES_ONLY/VIDEOS_ONLY.
- Renderer, TTS, timing de subtítulos, word budgets, `evaluate_duration_fitting`,
  ratios, `MAX_DURATION_REPAIRS`, `distribute_words`, scene planning.
- Web UI.

## Invariantes a preservar

- Repairs solo emiten `sceneNumber` + `voiceover`; `visualPlan` nunca en output de repair.
- Mismo número/orden de escenas; mínimo de palabras por escena.
- `maximumWords` del contrato bootstrap y duración TTS real como autoridad.
- Los prompts de repair NO deben contener literalmente `minimumWords` / `maximumWords`
  (los tests existentes lo exigen).
- `mediaPreference`/AUTO/MIXED siguen verdes.