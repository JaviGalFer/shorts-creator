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
MAX_SCENES_FOR_SHORT = 6
MIN_WORDS_PER_SCENE = 7

SYSTEM_PROMPT = """Eres un guionista senior especializado en Shorts/TikTok/Reels históricos con obsesión por la retención y la calidad visual documental.

Devuelve SOLO JSON válido, sin markdown, sin explicaciones.

## Reglas de ritmo para Short (<30s)
- Máximo 6 escenas (normalmente 4-6). Prefiere 5 escenas.
- Duración total: 25-30 segundos
- Cada escena: 4-7 segundos (mínimo 3.5s, evita micro-escenas)
- Palabras totales: ~45-55
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
4. Proponer searchQueries en inglés para buscar imágenes reales
5. Priorizar archivo histórico, mapas, documentos, carteles y retratos
6. Usar allowGeneratedImage=true solo cuando no exista material histórico razonable
7. Incluir negativePrompt cuando allowGeneratedImage=true
8. Mantener tono histórico, documental y sobrio
9. Evitar símbolos, banderas, uniformes o estética incorrecta para la época
10. Alternar tipos de asset entre escenas: no repetir el mismo tipo en escenas consecutivas
11. Para generated_image, usar imageGenerationPrompt en inglés con descripción visual detallada (iluminación, encuadre, colores, composición)
12. visualPrompt debe ser un fallback en INGLÉS con descripción fotográfica realista para banco de imágenes

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
Cada escena debe tener un editorialRole que define el propósito visual:

Roles disponibles:
- context_map: cuando el guion menciona geografía, territorio, fronteras. AssetType preferido: map, document.
- character_portrait: cuando el guion menciona una persona específica. AssetType preferido: portrait, historical_photograph, painting.
- military_technology: cuando el guion menciona armas, fortificaciones, barcos. AssetType preferido: historical_photograph, painting, document.
- civilian_impact: cuando el guion describe sufrimiento, vida cotidiana, refugiados. AssetType preferido: historical_photograph, document.
- battle_or_assault: cuando el guion describe combate, asedio, ataque. AssetType preferido: painting, historical_photograph.
- document_or_date: cuando el guion menciona un tratado, fecha, ley, carta. AssetType preferido: document, map.
- consequence_or_legacy: cuando el guion describe impacto histórico duradero. AssetType preferido: historical_photograph, painting.
- atmospheric_transition: solo para escenas puente sin contenido narrativo denso. Máximo 20% de escenas del vídeo. AssetType preferido: atmospheric_broll.

Reglas:
- atmospheric_transition NO puede usarse en más del 20% de las escenas del vídeo.
- generated_reconstruction no puede usarse en escenas consecutivas.
- Si el guion menciona una persona real, el rol debe ser character_portrait. No usar atmospheric_transition.
- Si el guion menciona una batalla o asedio, el rol debe ser battle_or_assault. No usar atmospheric_transition.
- Si el guion menciona una fecha o documento, el rol debe ser document_or_date.
- Alternar editorialRole entre escenas: no repetir el mismo rol en escenas consecutivas.
- Para mapas, incluir focalRegion (center|north|south|east|west), cropMode (full_map|region_zoom|detail), y overlayText (fecha/lugar).

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


def _build_duration_prompt_instruction(target_sec: int, min_sec: int, max_sec: int,
                                       strictness: str, retry: int = 0) -> str:
    word_budget_high = int(max_sec * SPOKEN_WORDS_PER_SECOND)
    word_budget_low = int(min_sec * SPOKEN_WORDS_PER_SECOND)
    target_words = int(target_sec * SPOKEN_WORDS_PER_SECOND)
    pause_ms = ESTIMATED_SCENE_PAUSE_MS
    lines = [
        f"## Restricción de duración ({strictness})",
        f"- Duración objetivo: {target_sec} segundos",
        f"- Ventana aceptable: {min_sec}-{max_sec} segundos",
        f"- Presupuesto de palabras: aproximadamente {target_words} palabras habladas (más pausas entre escenas de ~{pause_ms}ms cada una)",
        f"- Escenas: entre 4 y 6 (máximo 6 para vídeos <30s)",
        f"- Mínimo 7 palabras por escena. Prefiere 7-10 palabras.",
        f"- El CTA debe incluirse dentro de la voz en off de la última escena, no como escena separada.",
        f"- NO uses frases de relleno. Añade detalles narrativos concretos: años, cifras, nombres propios.",
        f"- Incluye al menos una fecha con año y al menos un nombre propio relevante.",
    ]
    if retry > 0:
        lines.append("")
        lines.append("## Intento anterior insuficiente")
        lines.append("El guion anterior no cumplía los requisitos. Debes corregirlo:")
        lines.append("- Añade más contexto histórico, descripciones visuales y detalles narrativos.")
        lines.append("- Cada escena debe tener 7-10 palabras en voiceover, mínimo 7.")
        lines.append("- DEBEN SER ENTRE 4 Y 6 ESCENAS. Máximo 6.")
        lines.append("- El CTA debe estar DENTRO de la última escena, nunca como escena  aparte.")
        lines.append("- Usa datos concretos: años, cifras, nombres propios.")
        lines.append("- Incluye al menos una fecha con año y un nombre propio relevante.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True, help="Historical topic for the video")
    parser.add_argument("--output", help="Output path for metadata.json (default: data/videos/{jobId}/metadata.json)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt and exit without calling API")
    parser.add_argument("--model", help="LLM model override")
    parser.add_argument("--duration-target", type=int, default=28, help="Target duration in seconds")
    parser.add_argument("--duration-min", type=int, default=25, help="Minimum duration in seconds")
    parser.add_argument("--duration-max", type=int, default=30, help="Maximum duration in seconds")
    parser.add_argument("--strictness", default="balanced",
                        choices=["strict", "balanced", "relaxed"],
                        help="Duration strictness level")
    args = parser.parse_args()

    env = load_env()
    api_key = env.get("LLM_API_KEY") or os.environ.get("LLM_API_KEY")
    model = args.model or env.get("LLM_MODEL") or "gpt-4o-mini"
    provider = env.get("LLM_PROVIDER") or "openai"

    if not api_key:
        print("ERROR: LLM_API_KEY not found in .env or environment")
        return 1

    target_dur = args.duration_target
    min_sec = args.duration_min
    max_sec = args.duration_max
    strictness = args.strictness

    duration_instruction = _build_duration_prompt_instruction(target_dur, min_sec, max_sec,
                                                               strictness, retry=0)

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

    while retries < max_attempts:
        if retries > 0:
            dur_inst_retry = _build_duration_prompt_instruction(
                target_dur, min_sec, max_sec, strictness, retry=retries
            )
            current_prompt = (
                f"Genera un guion histórico muy atractivo para vídeo vertical sobre: {args.topic}. "
                f"Quiero que el arranque tenga máxima retención.\n\n{dur_inst_retry}"
            )
            print(f"Retry {retries}/{max_attempts - 1}: generating more detailed script...")

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
        retry_history.append({
            "retry": retries,
            "wordCount": word_count,
            "sceneCount": scene_count,
            "spokenDurationSec": round(spoken_sec, 1),
            "pauseDurationSec": round(pause_sec, 1),
            "estimatedDurationSec": round(estimated_dur, 1),
        })
        print(f"  Attempt {retries + 1}: {word_count} words, estimated {estimated_dur:.1f}s "
              f"(target {target_dur}s, range {min_sec}-{max_sec}s)")

        # Check duration
        if strictness == "strict":
            margin = target_dur * 0.10
            duration_ok = (target_dur - margin) <= estimated_dur <= (target_dur + margin)
        elif strictness == "balanced":
            duration_ok = min_sec <= estimated_dur <= max_sec
        else:
            duration_ok = True  # relaxed

        if duration_ok:
            print(f"  Duration OK ({estimated_dur:.1f}s within range)")
            break

        retries += 1

    job_id = generate_job_id(args.topic)

    # ── Build request with full subtitle schema ────────────────────────
    request = {
        "topic": args.topic,
        "language": "es-ES",
        "format": "shorts-9x16",
        "duration": {
            "targetSec": target_dur,
            "minSec": min_sec,
            "maxSec": max_sec,
            "strictness": strictness,
            "spokenWordsPerMinute": SPOKEN_WORDS_PER_MINUTE,
            "estimatedScenePauseMs": ESTIMATED_SCENE_PAUSE_MS,
        },
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

    scene_count_ok = 4 <= scene_count <= MAX_SCENES_FOR_SHORT

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
            f"expected 4-{MAX_SCENES_FOR_SHORT}"
        )

    status = "SCRIPT_DRAFT" if all_ok else "REVIEW_REQUIRED"

    metadata = {
        "jobId": job_id,
        "status": status,
        "topic": args.topic,
        "requestedTopic": args.topic,
        "language": "es-ES",
        "format": "shorts-9x16",
        "targetDurationSeconds": target_dur,
        "request": request,
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
