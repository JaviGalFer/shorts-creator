#!/usr/bin/env python3

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path

from duration_profiles import add_duration_profile_args, resolve_requested_duration, calculate_word_budget

DOTENV_PATH = Path(__file__).resolve().parents[1] / ".env"

# Speech rate (Edge TTS Spanish, ~AlvaroNeural):
# Speech-only: ~160 WPM, but Edge TTS inserts ~1s pauses between sentences.
# Measured speech rate (3 runs, total 164 words / 88.104s): ~111.7 WPM.
# Using 110 as conservative spoken-only rate (not including scene pauses).
SPOKEN_WORDS_PER_MINUTE = 110
SPOKEN_WORDS_PER_SECOND = SPOKEN_WORDS_PER_MINUTE / 60.0

# Inter-scene pause added by Edge TTS between narration units.
# Each scene transition adds this pause to total duration.
ESTIMATED_SCENE_PAUSE_MS = 350

# For under-30 Shorts: 4-6 scenes, not 10.
# 10 micro-scenes inflate effective duration via cumulative pauses.
# With 5 transitions (6 scenes): 5 * 350ms = 1.75s pause overhead.
# With 9 transitions (10 scenes): 9 * 350ms = 3.15s pause overhead.
MAX_SCENES = 6
MIN_WORDS_PER_SCENE = 7

SYSTEM_PROMPT = """Eres un guionista senior especializado en Shorts/TikTok/Reels históricos con obsesión por la retención y la calidad visual documental.

Devuelve SOLO JSON válido, sin markdown, sin explicaciones.

## Reglas de ritmo
- Máximo 6 escenas (normalmente 4-6). Prefiere 5 escenas.
- La duración total, palabras totales y palabras por escena se especifican en las instrucciones dinámicas. Respeta esos valores.
- Las instrucciones dinámicas también especifican palabras mínimas, preferidas y máximas. Respétalas estrictamente.
- Mínimo 7 palabras por escena
- Frases contundentes, sin relleno
- El hook (primera escena) debe abrir con algo sorprendente (paradoja, amenaza, cifra, pregunta fuerte)
- El CTA debe incluirse DENTRO de la última escena, no como escena separada.
- NO crear una escena separada solo para CTA.

## Reglas de narración (voiceover)
- En español de España (no latinoamericano)
- Mínimo 7 palabras por escena
- DEBEN SER ENTRE 4 Y 6 ESCENAS. Mínimo 4, máximo 6. Prefiere 5.
- Tono divulgativo, dramático y preciso
- No inventar datos históricos
- Priorizar datos concretos: años, cifras, nombres propios
- Incluir al menos una fecha con año y un nombre propio en el guion
- Cada escena DEBE contribuir al total narrativo; no hay espacio para relleno
- El CTA de seguimiento ("síguenos", "suscríbete") debe estar DENTRO de la voz en off de la última escena, no como escena independiente

## Reglas de subtítulos (subtitle)
- Frase corta y memorable, máximo 7 palabras
- Debe reflejar la idea principal del voiceover

## Reglas de estrategia visual (visualPlan)
Cada escena debe tener un plan visual estructurado. NO uses prompts genéricos.

### Estrategias disponibles (strategy):
1. "historical_archive" — Fotografías históricas reales, retratos, pinturas, grabados. Para hechos con documentación visual disponible.
2. "map_or_document" — Mapas históricos, carteles, periódicos, tratados, cartas. Para movimientos territoriales, contextos políticos.
3. "atmospheric_broll" — Escenas atmosféricas (fuego, humo, lluvia, ruinas, mapas sobre mesa, libros, velas). Para transiciones o contexto emocional.
4. "generated_reconstruction" — Reconstrucción IA de escenas sin archivo disponible. Para ciudades desaparecidas, escenarios antiguos sin fotografía.

### Reglas visuales obligatorias:
1. Evitar prompts genéricos como "chaotic battlefield", "soldiers marching", "devastated city"
2. Proponer recursos visualmente específicos y variados entre escenas
3. Identificar entidades históricas reales cuando corresponda
4. Proponer searchQueries en inglés para buscar imágenes reales en Wikimedia Commons. Las queries deben incluir nombres propios de personas, lugares específicos, eventos históricos con año, o combinaciones exactas. Ejemplos válidos: "Brandenburg Gate Berlin 1989", "Map of Constantinople siege 1453", "Portrait of Francisco Pizarro". Ejemplos a evitar: "Berlin Wall fall footage", "old war photograph", "historical battle scene" — son demasiado genéricos para encontrar contenido en archivos.
5. Priorizar archivo histórico, mapas, documentos, carteles y retratos
6. Usar allowGeneratedImage=true solo cuando no exista material histórico razonable
7. Incluir negativePrompt cuando allowGeneratedImage=true
8. Mantener tono histórico, documental y sobrio
9. Evitar símbolos, banderas, uniformes o estética incorrecta para la época
10. Alternar tipos de asset entre escenas: no repetir el mismo tipo en escenas consecutivas
11. Para generated_image, usar imageGenerationPrompt en inglés con descripción visual detallada (iluminación, encuadre, colores, composición)
12. visualPrompt debe ser un fallback en INGLÉS con descripción fotográfica realista para banco de imágenes
13. Incluir al menos 2 searchQueries por escena en visualPlan.searchQueries. La primera debe ser la más específica (evento + lugar + año). La segunda debe ser alternativa con distinta formulación. Ejemplo: ["Berlin Wall being torn down at Brandenburg Gate November 1989", "crowd celebrating fall of Berlin Wall 1989"]
14. Cada searchQuery debe contener al menos un nombre propio (persona, lugar, evento) Y un año o período concreto. Las queries sin nombre propio ni año serán rechazadas por el sistema de búsqueda.

## Secuenciación visual (visualSequence)
Cada escena debe tener una microsecuencia de 1-3 segmentos visuales.

### Reglas de segmentación (OBLIGATORIAS):
- Escenas ≤4s: 1 segmento (sin división)
- Escenas 5-7s: EXACTAMENTE 2 segmentos. No uses 1 segmento.
- Escenas ≥8s: 2-3 segmentos. No uses 1 segmento.
- Toda escena >4s DEBE tener al menos 2 segmentos en visualSequence. Es una regla técnica obligatoria.
- No repetir assetType en segmentos consecutivos de la misma escena
- No repetir generated_reconstruction en escenas consecutivas
- generated_reconstruction: máximo 1 por escena
- historical_map: ideal como segmento inicial para contexto espacial
- Para document y map: durationFraction mayor para que se vea bien

### Reglas de composición:
- Si el assetType es historical_map o document, indicar en editorialReason si necesita centrado o zoom a región
- Para portrait, puede ocupar todo el segmento o ir acompañado de broll atmosférico
- Para atmospheric_broll, especificar qué ambiente concreto (amanecer, tormenta, humo, etc.)
- La suma de durationFraction de todos los segmentos debe ser exactamente 1.0
- transition posible: "cut" (corte seco) o "fade" (fundido de 0.5s)

### Reglas de rol editorial (editorialRole)
Cada escena debe tener un editorialRole que define el propósito visual. La selección debe seguir las reglas deterministas a continuación. NO usar context_map como valor por defecto.

#### Árbol de decisión (evaluar en orden):
1. ¿La escena menciona una persona real específica? → character_portrait
2. ¿La escena describe combate, asedio, ataque o caída violenta? → battle_or_assault
3. ¿La escena describe armas, fortificaciones o tecnología militar? → military_technology
4. ¿La escena describe sufrimiento, vida cotidiana, refugiados o celebración popular? → civilian_impact
5. ¿La escena menciona un tratado, fecha con año, ley o carta? → document_or_date
6. ¿La escena describe geografía, territorio, fronteras, zonas de ocupación o rutas? → context_map
7. ¿La escena reflexiona sobre legado, memoria o impacto duradero? → consequence_or_legacy
8. ¿La escena es puente sin contenido narrativo denso? → atmospheric_transition (máx 20%)

#### Reglas de exclusión (NO usar estos roles si aplica lo siguiente):
- **context_map**: NO usar para escenas que describen un evento (caída, batalla, protesta, celebración). context_map es solo para contexto geográfico. Para eventos, usar civilian_impact, battle_or_assault o consequence_or_legacy según corresponda. Ejemplo: "El Muro de Berlín cayó en 1989" → battle_or_assault o civilian_impact, NO context_map.
- **character_portrait**: NO usar si no hay una persona histórica específica mencionada en la escena.
- **atmospheric_transition**: NO usar en más del 20% de escenas. NO usar si la escena tiene contenido narrativo sustancial.

#### Descripción detallada por rol:
- context_map: EXCLUSIVAMENTE para escenas donde el propósito visual principal es entender geografía, territorio, fronteras, zonas de ocupación, rutas o extensiones. El voiceover debe mencionar explícitamente lugares, regiones o extensiones territoriales. AssetType preferido: map, document.
- character_portrait: Una persona histórica específica es nombrada o implícita. AssetType preferido: portrait, historical_photograph, painting.
- military_technology: Armas, fortificaciones, barcos, vehículos militares. AssetType preferido: historical_photograph, painting, document.
- civilian_impact: Impacto en personas: sufrimiento, vida cotidiana, refugiados, celebraciones populares, reuniones familiares. AssetType preferido: historical_photograph, document.
- battle_or_assault: Combate activo, asedio, ataque, asalto, caída violenta de una ciudad/muro/régimen. AssetType preferido: painting, historical_photograph.
- document_or_date: Tratados, leyes, cartas, proclamas, fechas clave. AssetType preferido: document, map.
- consequence_or_legacy: Impacto histórico duradero, memoria, legado moderno, reflexión. AssetType preferido: historical_photograph, painting.
- atmospheric_transition: Escenas puente sin contenido narrativo denso. Máximo 20% de escenas. AssetType preferido: atmospheric_broll.

#### Reglas adicionales:
- Alternar editorialRole entre escenas: no repetir el mismo rol en escenas consecutivas.
- Para mapas, incluir focalRegion (center|north|south|east|west), cropMode (full_map|region_zoom|detail), y overlayText (fecha/lugar).
- generated_reconstruction no puede usarse en escenas consecutivas.

### Reglas de intent temporal (visualTemporalIntent)
Cada escena debe tener un visualTemporalIntent que clasifica si la escena describe un evento histórico concreto o un legado moderno:

Valores disponibles:
- "event_depiction" — La escena describe un evento histórico específico que ocurrió en el pasado (una batalla, una caída, una protesta, una construcción, un descubrimiento). Voiceover usa verbos en pasado y años/fechas concretas.
- "legacy_or_commemoration" — La escena reflexiona sobre el impacto duradero, memoria moderna, o legado actual. Voiceover usa presente o "hoy", "actualmente", "recuerda", "legado".
- "context_or_setup" — La escena proporciona contexto geográfico, político o social sin describir un evento específico.

Reglas:
- Si el editorialRole está en {context_map, character_portrait, battle_or_assault, military_technology, civilian_impact, document_or_date}, el visualTemporalIntent debe ser "event_depiction".
- Si el editorialRole es "consequence_or_legacy" y el voiceover describe el evento (verbos en pasado, año del evento), usar "event_depiction". Si describe el legado actual (presente, "hoy", "monumento"), usar "legacy_or_commemoration".
- Para escenas de transición atmosférica, usar "context_or_setup".

## Narrative Beats (narrativeBeats)
Cada escena DEBE incluir un array narrativeBeats que divide el voiceover en unidades semánticas.

### Reglas de segmentación por beats:
| Duración escena | Beats mínimos |
|----------------|--------------|
| ≤4s | 1 (opcional, puede omitirse) |
| 5-7s | EXACTAMENTE 2 beats |
| ≥8s | 2-3 beats |

### Reglas de contenido:
- Cada beat representa una idea o frase semántica completa dentro del voiceover.
- No dividir por tiempo arbitrario: cada beat debe contener una unidad de significado.
- startCueIndex y endCueIndex referencian índices de cues de subtítulos (0-based). Por ahora, estima secuencialmente.
- visualIntent describe qué se muestra visualmente (character_and_army, siege_technology, city_view, battle_action, document_evidence, consequence, context_map, portrait_focus).
- preferredAssetType: portrait_or_historical_art, historical_art_or_document, map_or_document, atmospheric, reconstruction.

### motionType en visualSequence
Cada segmento en visualSequence DEBE incluir un campo motionType que define el movimiento de cámara:

Tipos disponibles:
- "slow_zoom_in": zoom lento centrado (1.0→1.15)
- "slow_zoom_out": zoom out lento centrado (1.15→1.0)
- "pan_left": paneo horizontal de derecha a izquierda
- "pan_right": paneo horizontal de izquierda a derecha
- "pan_up": paneo vertical de abajo arriba
- "pan_down": paneo vertical de arriba abajo
- "static": sin movimiento
- "detail_crop": crop a detalle ampliado

Reglas de motionType:
- Cada segmento DEBE tener motionType.
- No repetir el mismo motionType en más de 2 segmentos consecutivos del mismo vídeo.
- Retratos: slow_zoom_in, pan_up, detail_crop.
- Mapas: slow_zoom_in, pan_left, pan_right.
- Grabados/pinturas: slow_zoom_in, detail_crop.
- Documentos: slow_zoom_in, detail_crop.
- B-roll: static, slow_zoom_in (suave, no exagerado).
- Alternar motionType entre beats de una misma escena si tienen distinto contenido visual.

## Formato JSON de salida
{
  "title": "Título atractivo del vídeo",
  "hook": "Frase de enganche principal",
  "summary": "Resumen de una línea",
  "totalTargetDurationSec": 60,
  "scenes": [
    {
      "sceneNumber": 1,
      "purpose": "Propósito narrativo de esta escena",
      "narrativeFunction": "hook|setup|escalation|turning_point|consequence|closing",
      "voiceover": "Texto narrado en español de España (12-18 palabras)",
      "subtitle": "Texto corto para subtítulo (máx 7 palabras)",
      "targetDurationSec": 6,
      "visualTemporalIntent": "event_depiction|legacy_or_commemoration|context_or_setup",
      "visualPrompt": "English description of a realistic photographic image for stock photo fallback",
      "imagePrompt": "3-5 keywords in Spanish for image search",
      "narrativeBeats": [
        {
          "beatIndex": 1,
          "text": "Frase del beat que coincide con parte del voiceover",
          "startCueIndex": 0,
          "endCueIndex": 1,
          "visualIntent": "character_and_army",
          "preferredAssetType": "portrait_or_historical_art"
        }
      ],
      "visualPlan": {
        "strategy": "historical_archive|map_or_document|atmospheric_broll|generated_reconstruction",
        "editorialRole": "context_map",
        "primaryAssetType": "historical_photograph|map|painting|document|broll",
        "secondaryAssetType": "map|document|portrait|broll|null",
        "period": "Historical period, e.g. Spanish Civil War, 1936-1939",
        "location": "Geographic location",
        "entities": ["Entity1", "Entity2"],
        "searchQueries": ["English search query 1", "English search query 2"],
        "imageGenerationPrompt": "Detailed English prompt for AI image generation (only if allowGeneratedImage=true)",
        "negativePrompt": "Things to avoid in AI generation (only if allowGeneratedImage=true)",
        "style": "historical documentary",
        "mood": "Descriptive mood",
        "preferredSources": ["wikimedia_commons", "pexels"],
        "allowGeneratedImage": false,
        "licenseRequired": "public_domain_or_cc",
        "visualImportance": "high|medium|low",
        "visualSequence": [
          {
            "segmentIndex": 1,
            "assetType": "historical_map",
            "searchQuery": "Map of Constantinople siege 1453",
            "durationFraction": 0.5,
            "transition": "cut",
            "editorialReason": "Mapa que muestra la posición de las murallas y el Cuerno de Oro",
            "focalRegion": "center",
            "cropMode": "region_zoom",
            "overlayText": "Constantinopla, 1453",
            "motionType": "slow_zoom_in"
          },
          {
            "segmentIndex": 2,
            "assetType": "atmospheric_broll",
            "searchQuery": "old stone walls fortress dramatic sky",
            "durationFraction": 0.5,
            "transition": "fade",
            "editorialReason": "Ambiente de fortaleza medieval para situar al espectador",
            "motionType": "pan_right"
          }
        ]
      }
    }
  ]
}"""


def load_env():
    env = {}
    if DOTENV_PATH.exists():
        for line in DOTENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def call_llm(prompt: str, api_key: str, model: str, provider: str = "openai") -> str:
    if provider == "openai":
        data = json.dumps({
            "model": model,
            "response_format": {"type": "json_object"},
            "temperature": 0.8,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
            content = result["choices"][0]["message"]["content"]
            content = re.sub(r'^```(?:json)?\s*', '', content.strip())
            content = re.sub(r'\s*```$', '', content.strip())
            return content
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def generate_job_id(topic: str) -> str:
    prefix = topic.split()[0].lower() if topic else "hist"
    prefix = re.sub(r'[^a-z0-9]', '', prefix)[:8]
    now = datetime.now(timezone.utc)
    return f"{prefix}-{now.strftime('%Y-%m-%d-%H%M%S')}"


def _count_voiceover_words(script_data: dict) -> int:
    total = 0
    for scene in script_data.get("scenes", []):
        vo = scene.get("voiceover", "")
        total += len(vo.split())
    return total


def _estimate_narration_duration_sec(word_count: int, scene_count: int) -> tuple[float, float, float]:
    spoken_sec = word_count / SPOKEN_WORDS_PER_SECOND
    transitions = max(0, scene_count - 1)
    pause_sec = transitions * ESTIMATED_SCENE_PAUSE_MS / 1000.0
    total_sec = spoken_sec + pause_sec
    return total_sec, spoken_sec, pause_sec


def _build_duration_prompt_instruction(budget: dict, strictness: str) -> str:
    target_sec = None
    min_sec = None
    max_sec = None
    for dur_field in ("targetSec", "target_sec", "target"):
        if dur_field in budget:
            target_sec = budget.get(dur_field)
            break
    for dur_field in ("minSec", "min_sec", "min"):
        if dur_field in budget:
            min_sec = budget.get(dur_field)
            break
    for dur_field in ("maxSec", "max_sec", "max"):
        if dur_field in budget:
            max_sec = budget.get(dur_field)
            break
    min_w = budget.get("minimumWords", 0)
    pref_w = budget.get("preferredWords", 0)
    max_w = budget.get("maximumWords", 0)
    pause_ms = budget.get("estimatedScenePauseMs", 350)
    per_scene_low = max(1, min_w // budget.get("sceneCount", 5)) if budget.get("sceneCount", 5) else 7
    per_scene_high = max(per_scene_low + 2, 7)
    lines = [
        f"## Restricción de duración ({strictness})",
    ]
    if target_sec is not None:
        lines.append(f"- Duración objetivo: {target_sec} segundos (ventana {min_sec}-{max_sec})")
    else:
        lines.append(f"- Ventana de duración: {min_sec}-{max_sec} segundos")
    lines.append(
        f"- El total de palabras habladas debe estar entre {min_w} y {max_w}, "
        f"con aproximadamente {pref_w} palabras objetivo "
        f"(pausas entre escenas de ~{pause_ms}ms cada una)"
    )
    lines.append(f"- Escenas: entre 4 y 6. Prefiere 5 escenas.")
    lines.append(f"- Mínimo 7 palabras por escena. Aproximadamente {per_scene_low}-{per_scene_high} palabras por escena.")
    lines.append(f"- El CTA debe incluirse dentro de la voz en off de la última escena, no como escena separada.")
    lines.append(f"- Distribuye los detalles históricos naturales entre las escenas: contexto, causas, desarrollo, consecuencias.")
    lines.append(f"- NO uses frases de relleno, CTA repetido, oraciones duplicadas ni pausas dramáticas falsas.")
    lines.append(f"- Incluye al menos una fecha con año y al menos un nombre propio relevante.")
    return "\n".join(lines)


def _build_retry_instruction(
    budget: dict,
    actual_word_count: int,
    actual_scene_count: int,
    estimated_dur: float,
) -> str:
    min_w = budget.get("minimumWords", 0)
    pref_w = budget.get("preferredWords", 0)
    max_w = budget.get("maximumWords", 0)
    missing = max(0, min_w - actual_word_count)
    excess = max(0, actual_word_count - max_w)
    pause_ms = budget.get("estimatedScenePauseMs", 350)
    dur_min = budget.get("minSec", 0)
    dur_max = budget.get("maxSec", 0)
    dur_target = budget.get("targetSec", 0)

    lines = [
        f"## Corrección de duración — intento anterior insuficiente",
        f"",
        f"El guion anterior tiene {actual_word_count} palabras habladas "
        f"en {actual_scene_count} escenas y estima {estimated_dur:.1f} segundos.",
        f"",
        f"El trabajo requiere:",
        f"- Duración: {dur_target}s objetivo, ventana {dur_min}-{dur_max}s",
        f"- Palabras totales: mínimo {min_w}, preferidas ~{pref_w}, máximo {max_w}",
        f"- Pausas entre escenas: ~{pause_ms}ms cada una",
    ]

    if missing > 0:
        lines.append("")
        lines.append(
            f"El guion se queda corto por aproximadamente {missing} palabras. "
            f"Añade aproximadamente entre {missing} y {missing + 5} palabras "
            f"significativas distribuidas naturalmente entre las escenas existentes. "
            f"Puedes expandir el contexto histórico, las causas, detalles del evento, "
            f"consecuencias o explicaciones. "
            f"No repitas el CTA, no insertes frases de relleno ni pausas artificiales."
        )
    elif excess > 0:
        lines.append("")
        lines.append(
            f"El guion excede por aproximadamente {excess} palabras. "
            f"Reduce aproximadamente {excess} palabras del contenido "
            f"manteniendo los datos históricos clave. "
            f"No uses frases de relleno."
        )

    lines.append("")
    lines.append("Reglas:")
    lines.append("- DEBEN SER ENTRE 4 Y 6 ESCENAS. Máximo 6.")
    lines.append("- El CTA debe estar DENTRO de la última escena, nunca como escena aparte.")
    lines.append("- Cada escena debe tener al menos 7 palabras.")
    lines.append("- Usa datos concretos: años, cifras, nombres propios.")
    lines.append("- No inventar datos históricos.")
    lines.append("- Incluye al menos una fecha con año y un nombre propio relevante.")

    return "\n".join(lines)


PROVISIONAL_SCENE_COUNT = 5


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True, help="Historical topic for the video")
    parser.add_argument("--output", help="Output path for metadata.json (default: data/videos/{jobId}/metadata.json)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt and exit without calling API")
    parser.add_argument("--model", help="LLM model override")
    add_duration_profile_args(parser)
    args = parser.parse_args()

    env = load_env()
    api_key = env.get("LLM_API_KEY") or os.environ.get("LLM_API_KEY")
    model = args.model or env.get("LLM_MODEL") or "gpt-4o-mini"
    provider = env.get("LLM_PROVIDER") or "openai"

    if not api_key:
        print("ERROR: LLM_API_KEY not found in .env or environment")
        return 1

    try:
        resolved = resolve_requested_duration(
            requested_sec=args.duration,
            requested_profile=args.duration_profile,
            explicit_target=args.duration_target,
            explicit_min=args.duration_min,
            explicit_max=args.duration_max,
            explicit_strictness=args.strictness,
        )
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    duration_profile_name = resolved["profile_name"]
    target_dur = resolved["targetSec"]
    min_sec = resolved["minSec"]
    max_sec = resolved["maxSec"]
    strictness = resolved["strictness"]
    requested_sec = resolved.get("requestedSec")
    requested_profile = resolved.get("requestedProfile")

    # ── Provisional word budget (before any LLM call) ──────────────────
    provisional_budget = calculate_word_budget(
        target_sec=target_dur,
        min_sec=min_sec,
        max_sec=max_sec,
        spoken_words_per_minute=SPOKEN_WORDS_PER_MINUTE,
        scene_count=PROVISIONAL_SCENE_COUNT,
        estimated_scene_pause_ms=ESTIMATED_SCENE_PAUSE_MS,
    )

    duration_instruction = _build_duration_prompt_instruction(provisional_budget, strictness)

    user_prompt = (
        f"Genera un guion histórico muy atractivo para vídeo vertical sobre: {args.topic}. "
        f"Quiero que el arranque tenga máxima retención, que cada escena tenga un plan visual detallado "
        f"con visualPlan Y visualSequence, y que la progresión visual sea coherente alternando tipos de "
        f"asset entre escenas. IMPORTANTE: Toda escena de más de 4 segundos DEBE tener 2 o más segmentos "
        f"en visualSequence. También DEBE incluir narrativeBeats array en cada escena y motionType en cada "
        f"segmento de visualSequence. Es una regla técnica obligatoria.\n\n"
        f"{duration_instruction}"
    )

    if args.dry_run:
        print("=== SYSTEM PROMPT ===")
        print(SYSTEM_PROMPT)
        print("\n=== USER PROMPT ===")
        print(user_prompt)
        print("\n=== MODEL ===")
        print(f"provider={provider}, model={model}")
        return 0

    print(f"Generating script for topic: {args.topic}")
    print(f"Using model: {model} ({provider})")
    print(f"Duration target: {target_dur}s, min: {min_sec}s, max: {max_sec}s, strictness: {strictness}")

    # ── Retry loop ────────────────────────────────────────────────────
    # max_attempts: total LLM calls permitted (initial + retries)
    # max_attempts=2 means 1 initial + up to 1 retry
    script_data: dict = {}
    retries = 0
    max_attempts = 2
    retry_history = []
    current_prompt = user_prompt
    final_budget = dict(provisional_budget)

    while retries < max_attempts:
        if retries > 0:
            word_count = _count_voiceover_words(script_data)
            scene_count = len(script_data.get("scenes", []))
            estimated_dur, _, _ = _estimate_narration_duration_sec(word_count, scene_count)
            retry_budget = calculate_word_budget(
                target_sec=target_dur,
                min_sec=min_sec,
                max_sec=max_sec,
                spoken_words_per_minute=SPOKEN_WORDS_PER_MINUTE,
                scene_count=scene_count,
                estimated_scene_pause_ms=ESTIMATED_SCENE_PAUSE_MS,
            )
            retry_inst = _build_retry_instruction(retry_budget, word_count, scene_count, estimated_dur)
            current_prompt = (
                f"Genera un guion histórico muy atractivo para vídeo vertical sobre: {args.topic}. "
                f"Quiero que el arranque tenga máxima retención.\n\n{retry_inst}"
            )
            print(f"Retry {retries}/{max_attempts - 1}: generated {word_count} words, "
                  f"estimated {estimated_dur:.1f}s, need {retry_budget['minimumWords']}-{retry_budget['maximumWords']} words")

        try:
            content = call_llm(current_prompt, api_key, model, provider)
        except Exception as e:
            print(f"ERROR calling LLM: {e}")
            return 1

        try:
            script_data = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"ERROR parsing LLM response as JSON: {e}")
            print(f"Raw response: {content[:500]}")
            return 1

        word_count = _count_voiceover_words(script_data)
        scene_count = len(script_data.get("scenes", []))
        estimated_dur, spoken_sec, pause_sec = _estimate_narration_duration_sec(word_count, scene_count)

        # Recalculate budget with actual scene count
        final_budget = calculate_word_budget(
            target_sec=target_dur,
            min_sec=min_sec,
            max_sec=max_sec,
            spoken_words_per_minute=SPOKEN_WORDS_PER_MINUTE,
            scene_count=scene_count,
            estimated_scene_pause_ms=ESTIMATED_SCENE_PAUSE_MS,
        )

        print(f"  Attempt {retries + 1}: {word_count} words, estimated {estimated_dur:.1f}s "
              f"(target {target_dur}s, range {min_sec}-{max_sec}s, "
              f"budget {final_budget['minimumWords']}-{final_budget['preferredWords']}-{final_budget['maximumWords']})")

        # Check duration
        if strictness == "strict":
            margin = target_dur * 0.10
            duration_ok = (target_dur - margin) <= estimated_dur <= (target_dur + margin)
        elif strictness == "balanced":
            duration_ok = min_sec <= estimated_dur <= max_sec
        else:
            duration_ok = True  # relaxed

        # Determine reason for retry history
        if duration_ok:
            retry_reason = "in_range"
            retry_instruction = "none_needed"
        elif word_count < final_budget["minimumWords"]:
            retry_reason = "below_minimum_words"
            retry_instruction = "expand_factual_content"
        elif word_count > final_budget["maximumWords"]:
            retry_reason = "above_maximum_words"
            retry_instruction = "reduce_content"
        else:
            retry_reason = "duration_out_of_range"
            retry_instruction = "expand_content"

        retry_entry = {
            "retry": retries,
            "reason": retry_reason,
            "actualWordCount": word_count,
            "minimumWords": final_budget["minimumWords"],
            "preferredWords": final_budget["preferredWords"],
            "maximumWords": final_budget["maximumWords"],
            "estimatedDurationSec": round(estimated_dur, 1),
            "instructionType": retry_instruction,
        }
        retry_history.append(retry_entry)

        if duration_ok:
            print(f"  Duration OK ({estimated_dur:.1f}s within range)")
            break

        retries += 1

    job_id = generate_job_id(args.topic)

    # ── Build request with full subtitle schema ────────────────────────
    duration_dict = {
        "targetSec": target_dur,
        "minSec": min_sec,
        "maxSec": max_sec,
        "strictness": strictness,
        "spokenWordsPerMinute": SPOKEN_WORDS_PER_MINUTE,
        "estimatedScenePauseMs": ESTIMATED_SCENE_PAUSE_MS,
    }
    if requested_sec is not None:
        duration_dict["requestedSec"] = requested_sec
    if requested_profile is not None:
        duration_dict["requestedProfile"] = requested_profile
    request = {
        "topic": args.topic,
        "language": "es-ES",
        "format": "shorts-9x16",
        "durationProfile": duration_profile_name,
        "duration": duration_dict,
        "voice": {
            "provider": "edge_tts",
            "voiceId": "es-ES-AlvaroNeural",
        },
        "subtitles": {
            "enabled": True,
            "timingProvider": "auto",
            "style": "shorts_upper_dynamic",
            "position": "upper_middle",
            "fontSize": 64,
            "outline": 4,
            "shadow": 2,
            "backgroundBox": False,
            "globalOffsetMs": 0,
        },
        "visuals": {
            "mode": "images",
            "allowGeneratedImages": False,
        },
        "editorialOverlays": {
            "enabled": False,
        },
        "music": {
            "enabled": False,
            "source": "none",
            "path": None,
            "volumeDb": -24,
            "duckUnderVoice": True,
            "fadeInMs": 300,
            "fadeOutMs": 500,
        },
    }

    word_count = _count_voiceover_words(script_data)
    scene_count = len(script_data.get("scenes", []))
    estimated_dur, spoken_sec, pause_sec = _estimate_narration_duration_sec(word_count, scene_count)

    scene_count_ok = 4 <= scene_count <= MAX_SCENES

    duration_ok_after_retries = False
    if strictness == "strict":
        margin = target_dur * 0.10
        duration_ok_after_retries = (target_dur - margin) <= estimated_dur <= (target_dur + margin)
    elif strictness == "balanced":
        duration_ok_after_retries = min_sec <= estimated_dur <= max_sec
    else:
        duration_ok_after_retries = True

    all_ok = duration_ok_after_retries and scene_count_ok

    review_reasons = []
    if not duration_ok_after_retries:
        review_reasons.append(
            f"DURATION_OUT_OF_RANGE: estimated={estimated_dur:.1f}s "
            f"(spoken={spoken_sec:.1f}s + pauses={pause_sec:.1f}s), "
            f"target={target_dur}s, min={min_sec}s, max={max_sec}s, "
            f"words={word_count}, scenes={scene_count}"
        )
    if not scene_count_ok:
        review_reasons.append(
            f"SCENE_COUNT_OUT_OF_RANGE: got {scene_count} scenes, "
            f"expected 4-{MAX_SCENES}"
        )

    status = "SCRIPT_DRAFT" if all_ok else "REVIEW_REQUIRED"

    resolved_config = {
        "duration": {
            "targetSec": target_dur,
            "minSec": min_sec,
            "maxSec": max_sec,
            "strictness": strictness,
            "spokenWordsPerMinute": SPOKEN_WORDS_PER_MINUTE,
            "estimatedScenePauseMs": ESTIMATED_SCENE_PAUSE_MS,
        },
        "durationProfile": duration_profile_name,
    }

    metadata = {
        "jobId": job_id,
        "status": status,
        "topic": args.topic,
        "requestedTopic": args.topic,
        "language": "es-ES",
        "format": "shorts-9x16",
        "targetDurationSeconds": target_dur,
        "durationProfile": duration_profile_name,
        "request": request,
        "resolvedConfig": resolved_config,
        "script": script_data,
        "durationContract": {
            "targetSec": target_dur,
            "minSec": min_sec,
            "maxSec": max_sec,
            "strictness": strictness,
            "spokenWordsPerMinute": SPOKEN_WORDS_PER_MINUTE,
            "estimatedScenePauseMs": ESTIMATED_SCENE_PAUSE_MS,
            "wordCount": word_count,
            "sceneCount": scene_count,
            "spokenDurationSec": round(spoken_sec, 1),
            "pauseDurationSec": round(pause_sec, 1),
            "estimatedDurationSec": round(estimated_dur, 1),
            "minimumWords": final_budget["minimumWords"],
            "preferredWords": final_budget["preferredWords"],
            "maximumWords": final_budget["maximumWords"],
            "pauseSec": final_budget["pauseSec"],
            "retries": retries,
            "retryHistory": retry_history,
            "status": "PASS" if all_ok else "FAIL",
        },
        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }

    if review_reasons:
        metadata["reviewReasons"] = review_reasons
        for r in review_reasons:
            print(f"REVIEW_REQUIRED: {r}")

    if args.output:
        out_path = Path(args.output).resolve()
    else:
        base = Path(__file__).resolve().parents[1]
        out_path = base / "data" / "videos" / job_id / "metadata.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")

    total_beats = sum(len(s.get("narrativeBeats", [])) for s in script_data.get("scenes", []))
    total_with_motion = sum(
        1 for s in script_data.get("scenes", [])
        for seg in s.get("visualPlan", {}).get("visualSequence", [])
        if seg.get("motionType")
    )

    print(json.dumps({
        "jobId": job_id,
        "path": str(out_path),
        "scenes": len(script_data.get("scenes", [])),
        "totalDuration": script_data.get("totalTargetDurationSec", 0),
        "title": script_data.get("title", ""),
        "narrativeBeats": total_beats,
        "segmentsWithMotion": total_with_motion,
        "wordCount": word_count,
        "spokenDurationSec": round(spoken_sec, 1),
        "pauseDurationSec": round(pause_sec, 1),
        "estimatedDurationSec": round(estimated_dur, 1),
        "durationContractStatus": "PASS" if all_ok else "FAIL",
        "retries": retries,
        "status": status,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
