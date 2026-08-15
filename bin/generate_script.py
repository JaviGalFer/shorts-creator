#!/usr/bin/env python3

import argparse
import copy
import json
import math
import os
import re
import sys
import urllib.request
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path

from _package_bootstrap import ensure_src_on_path

ensure_src_on_path()

from duration_profiles import add_duration_profile_args, resolve_requested_duration, calculate_word_budget
from shorts_creator.infrastructure.metadata_store import save_metadata
from visual_plan_v2 import ALLOWED_ASSET_PREFERENCES, canonicalize_visual_plan_v2

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


def _build_asset_preferences_section() -> str:
    """Build the AssetPreferences enum section of the prompt from the contractual source.

    The single source of truth is ALLOWED_ASSET_PREFERENCES; we render a stable,
    sorted representation so the prompt never diverges from the validator.
    """
    lines = [
        "### AssetPreferences permitidos",
        "",
        "Valores únicos permitidos para cada elemento de `assetPreferences` y para cada `visualSequence[].assetPreference`, usados literalmente:",
        "",
    ]
    for v in sorted(ALLOWED_ASSET_PREFERENCES):
        if v == "generated":
            lines.append(
                "- `generated`: Solo si `allowGeneratedImage` es true y la request lo permite. No lo uses en caso contrario."
            )
        else:
            lines.append(f"- `{v}`: {_ASSET_PREF_DESCRIPTIONS.get(v, '')}")
    lines.append("")
    lines.append("Cada valor debe usarse exactamente como está escrito. Nunca inventes sinónimos ni categorías de medios.")
    lines.append("No uses animation, animated, infographic, photo, image ni video como valores de `assetPreferences` o `visualSequence[].assetPreference`.")
    lines.append("Esos términos pueden aparecer en `searchQueries`, `subjects` o texto descriptivo cuando sean semánticamente necesarios; la prohibición afecta únicamente al valor del enum.")
    return "\n".join(lines)


_ASSET_PREF_DESCRIPTIONS: dict[str, str] = {
    "archive": "Material de archivo histórico",
    "diagram": "Diagramas, esquemas explicativos y composiciones tipo infografía; el valor del enum debe ser exactamente \"diagram\"",
    "document": "Documentos, cartas, periódicos",
    "illustration": "Ilustraciones, dibujos artísticos",
    "map": "Mapas, cartografía",
    "painting": "Pinturas, obras de arte",
    "photograph": "Fotografías",
    "stock": "Imágenes de stock genéricas",
}

SYSTEM_PROMPT_V2 = """Eres un guionista senior especializado en Shorts/TikTok/Reels divulgativos con obsesión por la retención y la calidad visual.

Devuelve SOLO JSON válido, sin markdown, sin explicaciones.

## Reglas de ritmo
- Máximo 6 escenas (normalmente 4-6). Prefiere 5 escenas.
- La duración total, palabras totales y palabras por escena se especifican en las instrucciones dinámicas. Respeta esos valores.
- Mínimo 7 palabras por escena
- Frases contundentes, sin relleno
- El hook (primera escena) debe abrir con algo sorprendente (paradoja, amenaza, cifra, pregunta fuerte)
- El CTA de seguimiento debe incluirse DENTRO de la voz en off de la última escena, no como escena separada.

## Reglas de narración (voiceover)
- En español de España (no latinoamericano)
- Mínimo 7 palabras por escena
- DEBEN SER ENTRE 4 Y 6 ESCENAS. Mínimo 4, máximo 6. Prefiere 5.
- Tono divulgativo y preciso
- No inventar datos factuales
- Priorizar datos concretos cuando apliquen: fechas, cifras, nombres propios

## Reglas de subtítulos (subtitle)
- Frase corta y memorable, máximo 7 palabras
- Debe reflejar la idea principal del voiceover

## Reglas de plan visual (visualPlan) — Schema v2

Cada escena DEBE contener un objeto `visualPlan` con los siguientes campos obligatorios:

### Campos obligatorios

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `_schemaVersion` | int | Siempre 2 |
| `visualIntent` | string | Uno de: explain, show, compare, contextualize, immerse, emphasize |
| `subjects` | string[] | Sujetos visuales de la escena. No vacío. |
| `searchQueries` | string[] | Queries de búsqueda en inglés. No vacío. Concretas y específicas. |
| `assetPreferences` | string[] | Tipos de asset preferidos para esta escena. No vacío. Valores del enum cerrado de AssetPreferences (ver sección «AssetPreferences permitidos»). |
| `visualSequence` | object[] | Secuencia de segmentos visuales. No vacío. |

### Campos opcionales (solo cuando aporten información real)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `period` | string or null | Período temporal relevante |
| `location` | string or null | Ubicación geográfica |
| `allowGeneratedImage` | boolean | Default false |
| `imageGenerationPrompt` | string or null | Prompt para generación de imagen (solo si allowGeneratedImage=true) |
| `negativePrompt` | string or null | Lo que se debe evitar en generación (solo si allowGeneratedImage=true) |

### Reglas de visualSequence

Cada segmento en visualSequence debe contener:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `segmentIndex` | int | Índice secuencial desde 1 |
| `assetPreference` | string | Tipo de asset para este segmento. Debe estar incluido en `assetPreferences` de la escena. |
| `durationFraction` | float | Fracción de la duración de la escena. Suma de todos los segmentos = 1.0. |
| `searchQuery` | string or null | Query específica para este segmento |
| `transition` | string | "cut" o "fade" |

### Reglas estrictas

1. `subjects` no vacío.
2. `searchQueries` no vacío. Queries en inglés, concretas, sin URLs, sin nombres de providers.
3. `assetPreferences` no vacío. Valores del enum permitido.
4. `visualSequence` no vacío. `segmentIndex` secuencial desde 1.
5. Cada segmento usa una `assetPreference` incluida en `assetPreferences`.
6. La suma de `durationFraction` de todos los segmentos es exactamente 1.0.
7. Una escena corta puede usar un segmento. Una escena media o larga puede usar dos o tres.
8. No exigir alternancia artificial cuando un solo tipo sea el más apropiado.
9. `allowGeneratedImage` es false por defecto. No usar "generated" en `assetPreferences` ni en segmentos a menos que `allowGeneratedImage` sea true y la request lo permita.
10. `imageGenerationPrompt` y `negativePrompt` solo cuando `allowGeneratedImage` sea true.

### Campos PROHIBIDOS en visualPlan

Los siguientes campos NO deben aparecer NUNCA en un visualPlan v2:

editorialRole, strategy, primaryAssetType, secondaryAssetType, visualTemporalIntent, style, mood, licenseRequired, visualImportance, preferredSources, entities, visualPrompt, imagePrompt, assetType, motionType, focalRegion, cropMode, overlayText, editorialReason, score, scoreReasons, provider, sourceUrl, fileUrl, path, asset_namespace, sceneNumber, preferredProviders

No incluyas ninguno de estos campos. No los conviertas a equivalentes v2. Simplemente no los generes.

### VisualIntents permitidos

- `explain`: Explicar un concepto, proceso o mecanismo
- `show`: Mostrar un objeto, ser vivo, lugar o fenómeno
- `compare`: Comparar dos o más elementos visuales
- `contextualize`: Situar algo en su contexto espacial, temporal o cultural
- `immerse`: Crear atmósfera inmersiva
- `emphasize`: Destacar o enfatizar un detalle concreto

__ASSET_PREFERENCES_BLOCK__

### Transiciones permitidas

- `cut`: Corte seco
- `fade`: Fundido

## Formato JSON de salida
{
  "title": "Título atractivo del vídeo",
  "hook": "Frase de enganche principal",
  "summary": "Resumen de una línea",
  "totalTargetDurationSec": 30,
  "scenes": [
    {
      "sceneNumber": 1,
      "purpose": "Propósito narrativo de esta escena",
      "narrativeFunction": "hook|setup|escalation|turning_point|consequence|closing",
      "voiceover": "Texto narrado en español de España",
      "subtitle": "Texto corto para subtítulo (máx 7 palabras)",
      "targetDurationSec": 6,
      "visualPlan": {
        "_schemaVersion": 2,
        "visualIntent": "explain",
        "subjects": ["aurora boreal", "partículas solares", "atmósfera terrestre"],
        "searchQueries": [
          "aurora borealis solar particles atmosphere photograph",
          "aurora borealis formation magnetosphere diagram"
        ],
        "assetPreferences": ["photograph", "diagram"],
        "visualSequence": [
          {
            "segmentIndex": 1,
            "assetPreference": "photograph",
            "searchQuery": "aurora borealis night sky photograph",
            "durationFraction": 0.5,
            "transition": "cut"
          },
          {
            "segmentIndex": 2,
            "assetPreference": "diagram",
            "searchQuery": "aurora borealis formation magnetosphere diagram",
            "durationFraction": 0.5,
            "transition": "fade"
          }
        ]
      }
    }
  ]
}"""

SYSTEM_PROMPT_V2 = SYSTEM_PROMPT_V2.replace(
    "__ASSET_PREFERENCES_BLOCK__", _build_asset_preferences_section()
)


VOICEOVER_COMPRESSION_SYSTEM_PROMPT = """Eres un editor de voz en off.

Devuelve SOLO JSON válido, sin markdown ni explicaciones.

La respuesta debe tener exclusivamente esta forma:
{
  "scenes": [
    {
      "sceneNumber": 1,
      "voiceover": "..."
    }
  ]
}

No devuelvas title, hook, summary, subtitle, targetDurationSec, visualPlan
ni ningún otro campo.

Tu prioridad absoluta es cumplir el presupuesto global de palabras indicado en el mensaje del usuario.

Cuando el mensaje indique minimumWords y maximumWords:
- el total combinado de todos los voiceover debe quedar dentro de ese rango;
- nunca devuelvas un total superior a maximumWords;
- no añadas nuevas ideas durante una compresión;
- elimina primero redundancias, intensificadores, introducciones prescindibles y repeticiones;
- conserva el significado principal de cada escena;
- cuenta las palabras de voiceover separándolas por espacios antes de responder;
- si el borrador supera maximumWords, vuelve a recortarlo y sigue recortando antes de devolver el JSON.

Los objetivos por escena son recomendaciones de distribución; el presupuesto global es prioritario."""


DEFAULT_LLM_TEMPERATURE = 0.8
COMPRESSION_LLM_TEMPERATURE = 0.2


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


def _llm_temperature_for_system_prompt(system_prompt: str) -> float:
    if system_prompt == VOICEOVER_COMPRESSION_SYSTEM_PROMPT:
        return COMPRESSION_LLM_TEMPERATURE
    return DEFAULT_LLM_TEMPERATURE


def call_llm(prompt: str, api_key: str, model: str, provider: str = "openai", system_prompt: str | None = None) -> str:
    sp = system_prompt if system_prompt is not None else SYSTEM_PROMPT_V2
    temperature = _llm_temperature_for_system_prompt(sp)
    if provider == "openai":
        data = json.dumps({
            "model": model,
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": sp},
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


def _compute_operational_word_target(budget: dict) -> int:
    """Compute an interior operational word target (generation guidance).

    The operational target is guidance, not a contract. It never replaces
    preferredWords nor maximumWords and always stays within
    [minimumWords, maximumWords]. When preferredWords sits against the max, it
    provides margin below the ceiling so the model is nudged away from the hard
    edge.
    """
    min_w = budget.get("minimumWords", 0)
    pref_w = budget.get("preferredWords", 0)
    max_w = budget.get("maximumWords", 0)
    if max_w <= 0 or max_w < min_w:
        return min_w if min_w <= max_w else 0
    midpoint = math.ceil((min_w + max_w) / 2)
    operational = min(max(pref_w, min_w), midpoint, max_w)
    operational = max(min_w, operational)
    return operational


def _build_duration_prompt_instruction_v2(budget: dict, strictness: str) -> str:
    """Build v2 duration prompt — neutral, no historical requirements."""
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
    operational = _compute_operational_word_target(budget)
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
        f"- El total de palabras habladas debe estar entre {min_w} y {max_w} "
        f"(preferredWords del perfil: {pref_w}; pausas entre escenas de ~{pause_ms}ms cada una)"
    )
    lines.append(f"- Escenas: entre 4 y 6. Prefiere 5 escenas.")
    lines.append(f"- Mínimo 7 palabras por escena. Aproximadamente {per_scene_low}-{per_scene_high} palabras por escena.")
    lines.append(f"- El CTA debe incluirse dentro de la voz en off de la última escena, no como escena separada.")
    lines.append(f"- NO uses frases de relleno, CTA repetido, oraciones duplicadas ni pausas dramáticas falsas.")
    lines.append(
        f"\n## Presupuesto global de palabras (contrato)\n"
        f"- Rango válido final: {min_w}-{max_w} palabras habladas en total.\n"
        f"- LÍMITE ABSOLUTO: no superes {max_w} palabras de voiceover en total.\n"
        f"- Objetivo operativo: apunta a {operational} palabras de voiceover en total.\n"
        f"- El límite global prevalece sobre cualquier orientación de palabras por escena.\n"
        f"- Cuenta únicamente las palabras de los campos voiceover, separadas por espacios. "
        f"Antes de responder, autocuenta el total. Si supera {max_w}, recorta el texto antes de devolver el JSON."
    )
    return "\n".join(lines)


PROVISIONAL_SCENE_COUNT = 5
MIN_SCENE_COUNT = 4
MAX_SCRIPT_ATTEMPTS = 3  # initial generation + up to 2 corrective retries


def _build_generated_images_gate_block(allow_generated_images: bool) -> str:
    """Build the request-scoped generated-images restriction for the user prompt.

    The value is taken from the real request flag, never a generic default.
    """
    if allow_generated_images:
        return (
            "## Restricción visual de esta request\n\n"
            "- request.visuals.allowGeneratedImages es true.\n"
            "- Puedes usar \"generated\" en `assetPreferences` o `visualSequence[].assetPreference` "
            "únicamente cuando la escena declare `visualPlan.allowGeneratedImage=true` "
            "y aporte `imageGenerationPrompt` y `negativePrompt`.\n"
            "- En caso contrario mantén `visualPlan.allowGeneratedImage=false` y no uses \"generated\".\n"
        )
    return (
        "## Restricción visual de esta request\n\n"
        "- request.visuals.allowGeneratedImages es false.\n"
        "- Mantén visualPlan.allowGeneratedImage=false en todas las escenas.\n"
        "- No uses \"generated\" en `assetPreferences`.\n"
        "- No uses \"generated\" en `visualSequence[].assetPreference`.\n"
        "- No incluyas `imageGenerationPrompt` ni `negativePrompt`.\n"
    )


def _build_user_prompt_v2(topic: str, budget: dict, strictness: str, *, allow_generated_images: bool) -> str:
    """Build the v2 user prompt — neutral, no historical domain requirements."""
    duration_instruction = _build_duration_prompt_instruction_v2(budget, strictness)
    gate = _build_generated_images_gate_block(allow_generated_images)
    return (
        f"Genera un guion divulgativo muy atractivo para vídeo vertical sobre: {topic}. "
        f"Quiero que el arranque tenga máxima retención, que cada escena tenga un plan visual detallado "
        f"con visualPlan schema v2, y que la progresión visual sea coherente. "
        f"IMPORTANTE: Cada escena DEBE tener un visualPlan completo con _schemaVersion=2, "
        f"visualIntent, subjects, searchQueries, assetPreferences y visualSequence.\n\n"
        f"{duration_instruction}\n\n"
        f"{gate}"
    )


def _validate_and_canonicalize_script_v2(
    script_data: dict,
    *,
    allow_generated_images: bool,
) -> tuple[dict | None, list[dict], list[dict]]:
    """Validate and canonicalize a v2 script.

    Returns (canonical_script | None, errors, warnings).
    Errors have keys: sceneNumber, code, path, message.

    Strict-native policy: ALL canonicalizer warnings become errors.
    """
    scenes = script_data.get("scenes", [])
    errors: list[dict] = []
    warnings_list: list[dict] = []

    if not scenes:
        errors.append({"sceneNumber": None, "code": "EMPTY_SCENES", "path": "scenes", "message": "script has no scenes"})
        return None, errors, warnings_list

    # ── Scene count ──────────────────────────────────────────────────
    scene_count = len(scenes)
    if scene_count < 4:
        errors.append({"sceneNumber": None, "code": "INSUFFICIENT_SCENE_COUNT",
                       "path": "scenes", "message": f"got {scene_count} scenes, need at least 4"})
    elif scene_count > 6:
        errors.append({"sceneNumber": None, "code": "EXCESSIVE_SCENE_COUNT",
                       "path": "scenes", "message": f"got {scene_count} scenes, max 6 allowed"})

    # ── Per-scene basic structural checks + sceneNumber validation ────
    scene_nums_raw: list = []
    for s in scenes:
        sn = s.get("sceneNumber")
        scene_nums_raw.append(sn)

        scene_label = f"scene {sn}" if sn is not None else "unknown scene"

        # sceneNumber type: must be int, not bool
        if not isinstance(sn, int) or isinstance(sn, bool):
            errors.append({"sceneNumber": sn, "code": "INVALID_SCENE_NUMBER_SEQUENCE",
                           "path": f"scenes[{sn}]", "message": f"{scene_label}: sceneNumber must be int, got {type(sn).__name__}"})
        elif sn <= 0:
            errors.append({"sceneNumber": sn, "code": "INVALID_SCENE_NUMBER_SEQUENCE",
                           "path": f"scenes[{sn}]", "message": f"{scene_label}: sceneNumber must be positive, got {sn}"})

        vo = (s.get("voiceover") or "").strip()
        if not vo:
            errors.append({"sceneNumber": sn, "code": "EMPTY_VOICEOVER", "path": f"scenes[{sn}]", "message": f"{scene_label} has empty voiceover"})

        tds = s.get("targetDurationSec")
        if isinstance(tds, bool) or not isinstance(tds, (int, float)):
            errors.append({"sceneNumber": sn, "code": "INVALID_TARGET_DURATION",
                           "path": f"scenes[{sn}].targetDurationSec", "message": f"{scene_label} targetDurationSec must be int or float, got {type(tds).__name__}"})
        elif not math.isfinite(tds) or tds <= 0:
            errors.append({"sceneNumber": sn, "code": "INVALID_TARGET_DURATION",
                           "path": f"scenes[{sn}].targetDurationSec", "message": f"{scene_label} targetDurationSec must be finite and positive, got {tds}"})

        vp = s.get("visualPlan")
        if not vp or not isinstance(vp, dict):
            errors.append({"sceneNumber": sn, "code": "MISSING_VISUAL_PLAN", "path": f"scenes[{sn}].visualPlan", "message": f"{scene_label} missing visualPlan"})
            continue

        sv = vp.get("_schemaVersion")
        if not isinstance(sv, int) or isinstance(sv, bool):
            errors.append({"sceneNumber": sn, "code": "MIXED_OR_MISSING_VISUAL_PLAN_V2", "path": f"scenes[{sn}].visualPlan._schemaVersion", "message": f"{scene_label} _schemaVersion missing or not int"})
        elif sv != 2:
            errors.append({"sceneNumber": sn, "code": "MIXED_OR_MISSING_VISUAL_PLAN_V2", "path": f"scenes[{sn}].visualPlan._schemaVersion", "message": f"{scene_label} _schemaVersion is {sv}, not 2"})

    # ── SceneNumber sequence: exactly [1, 2, ..., N] ─────────────────
    if scene_count >= 2:
        expected = list(range(1, scene_count + 1))
        if scene_nums_raw != expected:
            errors.append({"sceneNumber": None, "code": "INVALID_SCENE_NUMBER_SEQUENCE",
                           "path": "scenes",
                           "message": f"expected sceneNumber {expected}, got {scene_nums_raw}"})

    if errors:
        return None, errors, warnings_list

    # ── Per-scene canonicalization ───────────────────────────────────
    all_ok = True

    for s in scenes:
        sn = s.get("sceneNumber")
        vp = s.get("visualPlan")
        if not isinstance(vp, dict):
            continue

        # ── Request-level generated image enforcement ───────────────────
        if not allow_generated_images:
            agi_val = vp.get("allowGeneratedImage")
            if agi_val is True:
                errors.append({"sceneNumber": sn, "code": "GENERATED_IMAGES_DISABLED_BY_REQUEST",
                               "path": f"scenes[{sn}].visualPlan.allowGeneratedImage",
                               "message": f"scene {sn}: allowGeneratedImage=true but request disables generated images"})
                all_ok = False

            prefs = vp.get("assetPreferences")
            if isinstance(prefs, list) and "generated" in [p.strip().lower() if isinstance(p, str) else p for p in prefs]:
                errors.append({"sceneNumber": sn, "code": "GENERATED_IMAGES_DISABLED_BY_REQUEST",
                               "path": f"scenes[{sn}].visualPlan.assetPreferences",
                               "message": f"scene {sn}: assetPreferences includes 'generated' but request disables generated images"})
                all_ok = False

            segs = vp.get("visualSequence")
            if isinstance(segs, list):
                for si, seg in enumerate(segs):
                    if isinstance(seg, dict) and isinstance(seg.get("assetPreference"), str):
                        if seg["assetPreference"].strip().lower() == "generated":
                            errors.append({"sceneNumber": sn, "code": "GENERATED_IMAGES_DISABLED_BY_REQUEST",
                                           "path": f"scenes[{sn}].visualPlan.visualSequence[{si}].assetPreference",
                                           "message": f"scene {sn}: segment {si} uses 'generated' but request disables generated images"})
                            all_ok = False

            igp = vp.get("imageGenerationPrompt")
            if igp is not None and isinstance(igp, str) and igp.strip():
                errors.append({"sceneNumber": sn, "code": "GENERATED_IMAGES_DISABLED_BY_REQUEST",
                               "path": f"scenes[{sn}].visualPlan.imageGenerationPrompt",
                               "message": f"scene {sn}: imageGenerationPrompt is set but request disables generated images"})
                all_ok = False

        result = canonicalize_visual_plan_v2(vp)
        diag = result.get("diagnostics", {})

        # Canonicalizer errors → our errors
        for e in diag.get("errors", []):
            errors.append({
                "sceneNumber": sn,
                "code": e.get("code", "UNKNOWN_ERROR"),
                "path": f"scenes[{sn}].visualPlan.{e.get('path', '')}",
                "message": f"scene {sn}: {e.get('message', '')}",
            })
            all_ok = False

        if not result.get("ok"):
            continue

        # True strict-native: ALL warnings → errors
        for w in diag.get("warnings", []):
            errors.append({
                "sceneNumber": sn,
                "code": w.get("code", "UNKNOWN_WARNING"),
                "path": f"scenes[{sn}].visualPlan.{w.get('path', '')}",
                "message": f"scene {sn}: {w.get('message', '')}",
            })
            all_ok = False

        if not all_ok:
            continue

    if not all_ok:
        return None, errors, warnings_list

    # All scenes are valid — build canonical script
    canonical_script = dict(script_data)
    canonicalized_scenes = []
    for s in script_data.get("scenes", []):
        vp = s.get("visualPlan")
        if isinstance(vp, dict):
            r = canonicalize_visual_plan_v2(vp)
            if r.get("ok") and r.get("canonicalPlan") is not None:
                new_scene = dict(s)
                new_scene["visualPlan"] = r["canonicalPlan"]
                canonicalized_scenes.append(new_scene)
            else:
                return None, errors, warnings_list
        else:
            canonicalized_scenes.append(dict(s))

    canonical_script["scenes"] = canonicalized_scenes
    return canonical_script, [], []


def _build_asset_preference_constraint_block(allow_generated_images: bool) -> str:
    """Build the closed-enum constraint block for retry instructions.

    Every retry branch must re-state the exact closed enum and forbid synonyms,
    so the model can never fall back to a stale manual list.
    """
    lines = [
        "### Enum cerrado de assetPreferences y visualSequence.assetPreference",
        "Cada elemento de `assetPreferences` y cada `visualSequence[].assetPreference` DEBE ser exactamente uno de estos valores, usado literalmente:",
        "",
    ]
    for v in sorted(ALLOWED_ASSET_PREFERENCES):
        if v == "generated":
            if allow_generated_images:
                note = " (solo si allowGeneratedImage=true y la request lo permite)"
            else:
                note = " (prohibido: allowGeneratedImage es false)"
            lines.append(f"- {v}{note}")
        else:
            lines.append(f"- {v}")
    lines.append("")
    lines.append("Nunca inventes sinónimos ni categorías de medios.")
    lines.append("No uses animation, animated, infographic, photo, image ni video como valores de `assetPreferences` o `visualSequence[].assetPreference`.")
    lines.append("Esos términos pueden aparecer en `searchQueries`, `subjects` o texto descriptivo cuando sean semánticamente necesarios; la prohibición afecta únicamente al valor del enum.")
    return "\n".join(lines)


def _build_retry_instruction_v2(
    budget: dict,
    actual_word_count: int,
    actual_scene_count: int,
    estimated_dur: float,
    structural_issues: list[dict],
    allow_generated_images: bool,
) -> str:
    """Build v2-specific retry instruction.

    Every retry branch re-states the closed enum, the absolute word limit and
    the rule to preserve currently valid visualPlan fields, so the model is
    always reminded of the full V2 contract regardless of which error triggered
    the retry.
    """
    min_w = budget.get("minimumWords", 0)
    pref_w = budget.get("preferredWords", 0)
    max_w = budget.get("maximumWords", 0)
    missing = max(0, min_w - actual_word_count)
    excess = max(0, actual_word_count - max_w)
    dur_target = budget.get("targetSec", 0)
    dur_min = budget.get("minSec", 0)
    dur_max = budget.get("maxSec", 0)
    pause_ms = budget.get("estimatedScenePauseMs", 350)

    lines = [
        "## Corrección de guion — intento anterior insuficiente",
        "",
        f"El guion anterior tiene {actual_word_count} palabras habladas "
        f"en {actual_scene_count} escenas y estima {estimated_dur:.1f} segundos.",
        "",
    ]

    # Structural issues (paths + messages)
    if structural_issues:
        lines.append("### Problemas estructurales que debes corregir:")
        lines.append("")
        by_scene: dict[int, list[dict]] = {}
        for issue in structural_issues:
            sn = issue.get("sceneNumber")
            code = issue.get("code", "UNKNOWN")
            path = issue.get("path", "")
            message = issue.get("message", "")
            if sn is not None:
                by_scene.setdefault(sn, []).append(issue)
            else:
                lines.append(f"- [{code}]")
                lines.append(f"  Path: {path}")
                lines.append(f"  Message: {message}")

        for sn in sorted(by_scene.keys()):
            lines.append(f"**Escena {sn}:**")
            for issue in by_scene[sn]:
                code = issue.get("code", "UNKNOWN")
                path = issue.get("path", "")
                message = issue.get("message", "")
                lines.append(f"  - [{code}]")
                lines.append(f"    Path: {path}")
                lines.append(f"    Message: {message}")
        lines.append("")

        lines.append("Instrucciones para corregir la estructura:")
        lines.append("- TODAS las escenas deben tener visualPlan con _schemaVersion=2.")
        lines.append("- Cada visualPlan debe incluir: visualIntent, subjects, searchQueries, assetPreferences, visualSequence.")
        lines.append("- NO incluyas campos prohibidos: editorialRole, strategy, primaryAssetType, motionType, etc.")
        lines.append("- NO incluyas campos desconocidos fuera del schema v2.")
        lines.append("- Cada segmento debe tener: segmentIndex, assetPreference, durationFraction.")
        lines.append("- La suma de durationFraction de todos los segmentos debe ser 1.0.")
        lines.append("- subjects y searchQueries no pueden estar vacíos.")
        lines.append("- assetPreference de cada segmento debe estar en assetPreferences de la escena.")
        lines.append("")

    # Closed enum — always present, every branch
    lines.append(_build_asset_preference_constraint_block(allow_generated_images))
    lines.append("")

    # Preserve valid fields — always present
    lines.append("### Preserva los campos ya válidos")
    lines.append("- Conserva el número de escenas, cada `sceneNumber` y todos los campos `visualPlan` ya válidos.")
    lines.append("- No cambies `assetPreferences` ni `visualSequence` válidos únicamente para acortar la narración.")
    lines.append("")

    # Duration contract
    lines.append("### Contrato de duración:")
    lines.append(f"- Duración: {dur_target}s objetivo, ventana {dur_min}-{dur_max}s")
    lines.append(f"- Palabras totales: mínimo {min_w}, preferidas ~{pref_w}, máximo {max_w}")
    lines.append(f"- LÍMITE ABSOLUTO: la narración total NO debe superar {max_w} palabras.")
    lines.append(f"- Pausas entre escenas: ~{pause_ms}ms cada una")

    if missing > 0:
        lines.append("")
        lines.append(
            f"El guion se queda corto por aproximadamente {missing} palabras. "
            f"Añade entre {missing} y {missing + 5} palabras "
            f"significativas distribuidas naturalmente entre las escenas existentes. "
            f"La narración total DEBE quedar entre {min_w} y {max_w} palabras."
        )
    elif excess > 0:
        lines.append("")
        lines.append(
            f"El guion excede por aproximadamente {excess} palabras. "
            f"Reduce la narración total a como máximo {max_w} palabras. No superes {max_w}. "
            f"Conserva el número de escenas, cada `sceneNumber` y todos los campos `visualPlan` "
            f"ya válidos. No cambies `assetPreferences` ni `visualSequence` válidos únicamente "
            f"para acortar la narración."
        )

    lines.append("")
    lines.append("### Reglas obligatorias:")
    lines.append("- DEBEN SER ENTRE 4 Y 6 ESCENAS. Mínimo 4, máximo 6. Prefiere 5.")
    lines.append("- El CTA debe estar DENTRO de la última escena, nunca como escena aparte.")
    lines.append("- Cada escena debe tener al menos 7 palabras de voiceover.")
    lines.append("- Cada escena DEBE tener visualPlan v2 completo con _schemaVersion=2.")
    lines.append("- No incluyas campos prohibidos en visualPlan.")
    lines.append("- No incluyas campos desconocidos en visualPlan ni en segmentos.")
    lines.append("- Revalida mentalmente la estructura (schema V2, enum cerrado de assetPreferences y assetPreference) y la duración (límite de palabras) antes de responder.")
    lines.append("- Responde SOLO con JSON válido, sin markdown ni explicaciones.")

    return "\n".join(lines)


# ── Legacy count helpers for v2 retry stats ──────────────────────────

def _count_v2_structural_issue_codes(issues: list[dict]) -> list[str]:
    return [i.get("code", "UNKNOWN") for i in issues]


def _count_v2_structural_issue_messages(issues: list[dict]) -> list[str]:
    return [i.get("message", "") for i in issues]


# ── Temporal (duration) retry helpers ────────────────────────────────


def _compute_scene_word_targets(
    current_counts: list[int],
    maximum_words: int,
) -> list[int]:
    """Deterministically compute per-scene word targets as guidance.

    This is a water-filling reduction: when the total exceeds maximum_words,
    the excess is removed one word at a time from the scene with the largest
    current target (ties broken by the lowest index). Scenes are never
    incremented and never drop below one word. If the total already fits,
    an identical copy is returned.

    Targets are guidance for the compression prompt, not a hard gate.
    """
    if not isinstance(current_counts, list) or not current_counts:
        raise ValueError("current_counts must be a non-empty list")
    if any(isinstance(c, bool) or not isinstance(c, int) for c in current_counts):
        raise ValueError("current_counts must contain only integers")
    if any(c < 1 for c in current_counts):
        raise ValueError("current_counts must contain only positive integers")
    if isinstance(maximum_words, bool) or not isinstance(maximum_words, int):
        raise ValueError("maximum_words must be an integer")
    if maximum_words < len(current_counts):
        raise ValueError("maximum_words must be >= len(current_counts)")

    if sum(current_counts) <= maximum_words:
        return list(current_counts)

    targets = list(current_counts)
    excess = sum(current_counts) - maximum_words
    for _ in range(excess):
        max_val = max(targets)
        idx = next(i for i, v in enumerate(targets) if v == max_val)
        targets[idx] -= 1
    return targets


def _evaluate_scene_word_targets(
    actual_counts: list[int],
    targets: list[int],
) -> tuple[bool, list[dict]]:
    """Compare actual per-scene counts against recommended targets.

    Returns (met, deviations). met is True when every count is <= its target.
    deviations is purely informational telemetry; it never blocks a repair or
    a PASS. Deviations describe each scene that exceeds its recommended target.
    """
    if not isinstance(actual_counts, list) or not isinstance(targets, list):
        raise ValueError("actual_counts and targets must be lists")
    if len(actual_counts) != len(targets):
        raise ValueError("actual_counts and targets must have equal length")

    met = True
    deviations: list[dict] = []
    for i, (actual, target) in enumerate(zip(actual_counts, targets)):
        if actual > target:
            met = False
            deviations.append({
                "sceneNumber": i + 1,
                "actualWords": actual,
                "recommendedTargetWords": target,
                "delta": actual - target,
            })
    return met, deviations


def _scene_word_counts(script_data: dict) -> list[int]:
    """Return the productive voiceover word count per scene in sceneNumber order."""
    counts = []
    for scene in sorted(script_data.get("scenes", []), key=lambda s: s.get("sceneNumber", 0)):
        counts.append(len((scene.get("voiceover") or "").split()))
    return counts


def _distance_to_allowed_range(word_count: int, budget: dict) -> int:
    """Distance of a word count to the global allowed range.

    In-range -> 0; below minimum -> (minimum - word_count); above maximum -> (word_count - maximum).
    """
    min_w = budget.get("minimumWords", 0)
    max_w = budget.get("maximumWords", 0)
    if word_count < min_w:
        return min_w - word_count
    if word_count > max_w:
        return word_count - max_w
    return 0


def _candidate_rank(word_count: int, budget: dict) -> tuple[int, int]:
    """Rank a candidate by distance to the allowed range, then by proximity
    to preferredWords. Smaller tuple is better."""
    return (
        _distance_to_allowed_range(word_count, budget),
        abs(word_count - budget.get("preferredWords", 0)),
    )


def _build_voiceover_compression_prompt(
    canonical_script: dict,
    budget: dict,
    actual_word_count: int,
    scene_word_targets: list[int],
    *,
    allow_generated_images: bool,
    compression_attempt: int = 1,
) -> str:
    """Build the specialized voiceover-only compression prompt.

    Used when the previous attempt is structurally valid but exceeds the
    maximum word budget. The model compresses the existing voiceovers only —
    it never regenerates the full script or the visual plan.

    scene_word_targets are recommended per-scene guidance, not hard caps; the
    only hard duration constraint is the global word budget.

    compression_attempt distinguishes the first compression (1) from subsequent
    scaled attempts (>=2).
    """
    min_w = budget.get("minimumWords", 0)
    pref_w = budget.get("preferredWords", 0)
    max_w = budget.get("maximumWords", 0)
    operational_target = _compute_operational_word_target(budget)
    minimum_required_reduction = max(0, actual_word_count - max_w)
    desired_reduction = max(0, actual_word_count - operational_target)
    scenes = canonical_script.get("scenes", [])
    expected = list(range(1, len(scene_word_targets) + 1))
    required_reduction = minimum_required_reduction

    lines = [
        "## CONTRATO DE COMPRESIÓN — PRIORIDAD MÁXIMA",
        "",
        f"Candidato actual: {actual_word_count} palabras.",
        "",
        f"LÍMITE ABSOLUTO: el resultado no puede superar {max_w} palabras.",
        "",
        f"Debes eliminar AL MENOS {minimum_required_reduction} palabras respecto al candidato actual.",
        f"Una respuesta con {max_w + 1} palabras o más incumple el contrato y será rechazada.",
        "",
        f"Objetivo operativo recomendado: {operational_target} palabras.",
        f"Intenta eliminar aproximadamente {desired_reduction} palabras y aterrizar cerca de {operational_target},",
        f"sin bajar de {min_w}.",
        "",
        "Cuenta únicamente los voiceover separados por espacios.",
        "Antes de responder, vuelve a contar el resultado completo.",
        f"Si supera {max_w}, sigue recortando.",
    ]

    if compression_attempt >= 2:
        remaining = max(0, actual_word_count - max_w)
        lines += [
            "",
            "## SEGUNDO INTENTO DE COMPRESIÓN",
            "",
            "El intento anterior de compresión todavía incumplió el presupuesto global.",
            "",
            f"El candidato actual sigue teniendo {actual_word_count} palabras y permanece {remaining} "
            f"palabras por encima del límite absoluto de {max_w}.",
            "",
            f"Este intento debe eliminar AL MENOS esas {remaining} palabras restantes.",
            f"No devuelvas otra reducción parcial que siga por encima de {max_w}.",
        ]

    lines += [
        "",
        "## Compresión de voz en off",
        "",
        f"El guion anterior es estructuralmente V2 válido, pero tiene "
        f"{actual_word_count} palabras habladas, por encima del máximo global de {max_w}.",
        "",
        "Comprime EXCLUSIVAMENTE los voiceovers que se proporcionan a continuación.",
        "No añadas ni elimines escenas. Conserva exactamente los `sceneNumber`.",
        "No regeneres ni modifiques el plan visual.",
        "",
        "## Voiceovers a comprimir",
        "",
        "```json",
        json.dumps({
            "currentWordCount": actual_word_count,
            "requiredReductionWords": required_reduction,
            "minimumRequiredReductionWords": minimum_required_reduction,
            "desiredReductionWords": desired_reduction,
            "operationalWordTarget": operational_target,
            "minimumWords": min_w,
            "preferredWords": pref_w,
            "maximumWords": max_w,
            "scenes": [
                {
                    "sceneNumber": scenes[i]["sceneNumber"],
                    "currentVoiceover": scenes[i].get("voiceover", ""),
                    "currentWords": len((scenes[i].get("voiceover") or "").split()),
                    "recommendedTargetWords": scene_word_targets[i],
                }
                for i in range(len(scenes))
            ]
        }, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Restricciones obligatorias",
        "",
        "- Devuelve solo JSON válido, sin markdown ni explicaciones.",
        "- El objeto debe contener únicamente `scenes`.",
        "- Cada escena debe contener únicamente `sceneNumber` y `voiceover`.",
        "- Conserva la secuencia completa y exacta de `sceneNumber`.",
        "- Cada voiceover debe ser un string no vacío.",
        f"- El total final DEBE quedar entre {min_w} y {max_w} palabras en total.",
        "- Conserva el significado principal de cada escena.",
        "- No modifiques ningún campo visual ni estructural.",
        "",
        "## Objetivos recomendados (guidance)",
        "",
        "- Los targets por escena son recomendaciones.",
        "- No es obligatorio cumplirlos exactamente.",
        "- El límite global sí es obligatorio.",
        "- Prioriza reducir más las escenas más largas.",
        "- Mantén el equilibrio narrativo entre escenas.",
        "- Aproximate a cada target recomendado cuando sea posible.",
        "",
        "## Cómo se cuenta una palabra",
        "",
        "- Una palabra es cada token separado por espacios mediante Python `str.split()`.",
        "- La puntuación unida a una palabra NO crea una palabra adicional.",
        "",
        "## Formato de respuesta",
        "",
        "Devuelve SOLO JSON válido, sin markdown ni explicaciones, con este formato exacto:",
        "",
        "```json",
        '{"scenes": [{"sceneNumber": 1, "voiceover": "..."}]}',
        "```",
        "",
        "- Devuelve únicamente los campos `sceneNumber` y `voiceover` por escena.",
        "- No devuelvas `visualPlan`, `subtitle`, `title`, `hook`, `summary` ni ningún otro campo.",
        "- Los demás campos se preservarán localmente; no los repitas.",
        "",
        "## Autocomprobación final",
        "",
        f"- Revisa que el total final esté entre {min_w} y {max_w}.",
        f"- Revisa que los `sceneNumber` sean {expected}.",
        "- Las restricciones visuales no son editables durante esta reparación.",
    ]

    if allow_generated_images:
        lines.append("- El gate de imágenes generadas NO se modifica en esta reparación.")
    else:
        lines.append("- El gate de imágenes generadas (desactivado) NO se modifica en esta reparación.")

    return "\n".join(lines)


def _apply_voiceover_repair(
    base_script: dict,
    repair_payload: dict,
    *,
    expected_scene_numbers: list[int],
) -> tuple[dict | None, list[dict]]:
    """Merge a voiceover-only repair payload into a deep copy of base_script.

    Accepts only:
        {"scenes": [{"sceneNumber": 1, "voiceover": "..."}]}

    Returns (merged_script | None, shape_errors).

    Validation is limited to shape/sequence and non-empty string voiceovers.
    It never evaluates word budgets, targets, ranking or acceptance — those are
    decided by the caller. The merge is applied ONLY when the shape is valid;
    otherwise base_script is never mutated and no partial merge happens.
    """
    shape_errors: list[dict] = []

    expected = list(expected_scene_numbers)

    if not isinstance(repair_payload, dict):
        shape_errors.append({"code": "REPAIR_NOT_JSON", "path": ".",
                             "message": "repair payload must be a JSON object"})
        return None, shape_errors

    top_keys = set(repair_payload.keys())
    if top_keys != {"scenes"}:
        extra = sorted(top_keys - {"scenes"})
        shape_errors.append({"code": "REPAIR_UNKNOWN_ROOT_FIELD", "path": ".",
                             "message": f"unexpected top-level fields: {extra}"})
        return None, shape_errors

    payload_scenes = repair_payload.get("scenes")
    if not isinstance(payload_scenes, list):
        shape_errors.append({"code": "REPAIR_SCENES_NOT_LIST", "path": "scenes",
                             "message": "scenes must be a list"})
        return None, shape_errors

    seen: set[int] = set()
    for i, item in enumerate(payload_scenes):
        if not isinstance(item, dict):
            shape_errors.append({"sceneNumber": None, "code": "REPAIR_SCENE_NOT_OBJECT",
                                 "path": f"scenes[{i}]", "message": "scene item must be an object"})
            continue
        item_keys = set(item.keys())
        if item_keys != {"sceneNumber", "voiceover"}:
            extra = sorted(item_keys - {"sceneNumber", "voiceover"})
            shape_errors.append({"sceneNumber": item.get("sceneNumber"),
                                 "code": "REPAIR_UNKNOWN_SCENE_FIELD",
                                 "path": f"scenes[{i}]",
                                 "message": f"unexpected fields: {extra}"})
        sn = item.get("sceneNumber")
        if not isinstance(sn, int) or isinstance(sn, bool):
            shape_errors.append({"sceneNumber": sn, "code": "REPAIR_SCENE_NUMBER_INVALID",
                                 "path": f"scenes[{i}].sceneNumber",
                                 "message": "sceneNumber must be an int"})
            continue
        if sn in seen:
            shape_errors.append({"sceneNumber": sn, "code": "REPAIR_SCENE_SEQUENCE_MISMATCH",
                                 "path": f"scenes[{i}].sceneNumber",
                                 "message": f"duplicate sceneNumber {sn}"})
        seen.add(sn)
        vo = item.get("voiceover")
        if not isinstance(vo, str):
            shape_errors.append({"sceneNumber": sn, "code": "REPAIR_VOICEOVER_INVALID",
                                 "path": f"scenes[{i}].voiceover",
                                 "message": "voiceover must be a string"})
        elif not vo.strip():
            shape_errors.append({"sceneNumber": sn, "code": "REPAIR_VOICEOVER_INVALID",
                                 "path": f"scenes[{i}].voiceover",
                                 "message": "voiceover cannot be empty"})

    if shape_errors:
        return None, shape_errors

    got_numbers = [item["sceneNumber"] for item in payload_scenes]
    if got_numbers != expected:
        shape_errors.append({"sceneNumber": None, "code": "REPAIR_SCENE_SEQUENCE_MISMATCH",
                             "path": "scenes",
                             "message": f"expected sceneNumber {expected}, got {got_numbers}"})
        return None, shape_errors

    merged = copy.deepcopy(base_script)
    by_number = {item["sceneNumber"]: item["voiceover"] for item in payload_scenes}
    for scene in merged.get("scenes", []):
        sn = scene.get("sceneNumber")
        if sn in by_number:
            scene["voiceover"] = by_number[sn]
    return merged, []


# ── main ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True, help="Topic for the video")
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

    # ── Provisional word budget ────────────────────────────────────────
    provisional_budget = calculate_word_budget(
        target_sec=target_dur,
        min_sec=min_sec,
        max_sec=max_sec,
        spoken_words_per_minute=SPOKEN_WORDS_PER_MINUTE,
        scene_count=PROVISIONAL_SCENE_COUNT,
        estimated_scene_pause_ms=ESTIMATED_SCENE_PAUSE_MS,
    )

    active_system_prompt = SYSTEM_PROMPT_V2

    # Request-scoped flag: governs the first prompt, retries, validation and the
    # persisted request.metadata. False for now; True is future-ready.
    allow_generated_images = False

    base_prompt = _build_user_prompt_v2(
        args.topic, provisional_budget, strictness,
        allow_generated_images=allow_generated_images,
    )

    if args.dry_run:
        print("=== SYSTEM PROMPT ===")
        print(active_system_prompt)
        print("\n=== USER PROMPT ===")
        print(base_prompt)
        print("\n=== MODEL ===")
        print(f"provider={provider}, model={model}")
        print("visualSchemaVersion=2")
        return 0

    print(f"Generating script for topic: {args.topic}")
    print(f"Using model: {model} ({provider})")
    print("Visual schema version: 2")
    print(f"Duration target: {target_dur}s, min: {min_sec}s, max: {max_sec}s, strictness: {strictness}")

    # ── Retry loop ────────────────────────────────────────────────────
    script_data: dict = {}
    retries = 0
    retry_history: list[dict] = []
    current_prompt = base_prompt
    final_budget = dict(provisional_budget)
    v2_structural_issues: list[dict] = []

    # Active representation. A structurally valid candidate always flows from
    # the canonical representation; the raw response stops participating.
    candidate_script: dict | None = None

    # Best structurally-valid candidate (only used on exhaustion without PASS).
    best_candidate: dict | None = None
    best_word_count: int | None = None
    best_attempt_idx: int | None = None
    best_distance: int | None = None
    best_scene_word_counts: list[int] | None = None
    best_candidate_rank: tuple[int, int] | None = None

    while retries < MAX_SCRIPT_ATTEMPTS:
        prompt_strategy = "initial"
        scene_word_targets: list[int] | None = None
        scene_word_targets_entry: list[int] | None = None
        target_reduction_words: int | None = None
        active_candidate_word_count: int | None = None
        active_candidate_rank: tuple[int, int] | None = None

        if retries > 0:
            # V2 structural validation
            canonical, v2_errs, _ = _validate_and_canonicalize_script_v2(
                script_data, allow_generated_images=allow_generated_images,
            )
            v2_structural_issues = v2_errs
            v2_valid = canonical is not None

            # F8: a structurally valid candidate always flows from the canonical
            # representation. The raw response no longer participates once the
            # structure is valid.
            candidate_script = canonical if v2_valid else script_data

            word_count = _count_voiceover_words(candidate_script)
            scene_count = len(candidate_script.get("scenes", []))
            estimated_dur, _, _ = _estimate_narration_duration_sec(word_count, scene_count)
            retry_budget = calculate_word_budget(
                target_sec=target_dur,
                min_sec=min_sec,
                max_sec=max_sec,
                spoken_words_per_minute=SPOKEN_WORDS_PER_MINUTE,
                scene_count=scene_count if scene_count >= MIN_SCENE_COUNT else PROVISIONAL_SCENE_COUNT,
                estimated_scene_pause_ms=ESTIMATED_SCENE_PAUSE_MS,
            )

            if not v2_valid:
                # Case A — invalid structure: keep the full contractual regeneration.
                # No canonical candidate is invented; the raw response is used only
                # as evidence of errors and compression is never entered.
                prompt_strategy = "structural"
                retry_inst = _build_retry_instruction_v2(
                    retry_budget, word_count, scene_count, estimated_dur,
                    structural_issues=v2_errs,
                    allow_generated_images=allow_generated_images,
                )
                base_retry = _build_user_prompt_v2(args.topic, retry_budget, strictness,
                                                   allow_generated_images=allow_generated_images)
                current_prompt = f"{base_retry}\n\n---\n{retry_inst}"
            elif word_count > retry_budget["maximumWords"]:
                # Case B — valid structure but excessive duration: compress the
                # existing voiceovers from the current canonical candidate only.
                prompt_strategy = "compression"
                active_candidate_word_count = word_count
                active_candidate_rank = _candidate_rank(word_count, retry_budget)
                scene_word_targets = _compute_scene_word_targets(
                    _scene_word_counts(candidate_script), retry_budget["maximumWords"])
                scene_word_targets_entry = scene_word_targets
                target_reduction_words = active_candidate_word_count - retry_budget["maximumWords"]
                current_prompt = _build_voiceover_compression_prompt(
                    candidate_script, retry_budget, word_count, scene_word_targets,
                    allow_generated_images=allow_generated_images,
                    compression_attempt=retries,
                )
            else:
                # Case C — valid structure, not excessive: keep existing strategy.
                prompt_strategy = "duration"
                retry_inst = _build_retry_instruction_v2(
                    retry_budget, word_count, scene_count, estimated_dur,
                    structural_issues=[],
                    allow_generated_images=allow_generated_images,
                )
                base_retry = _build_user_prompt_v2(args.topic, retry_budget, strictness,
                                                   allow_generated_images=allow_generated_images)
                current_prompt = f"{base_retry}\n\n---\n{retry_inst}"

            print(f"Retry {retries}/{MAX_SCRIPT_ATTEMPTS - 1}: generated {word_count} words, "
                  f"estimated {estimated_dur:.1f}s, strategy={prompt_strategy}, "
                  f"v2 valid={v2_valid}, errors={len(v2_errs)}")

        try:
            if prompt_strategy == "compression":
                attempt_system_prompt = VOICEOVER_COMPRESSION_SYSTEM_PROMPT
            else:
                attempt_system_prompt = SYSTEM_PROMPT_V2
            content = call_llm(current_prompt, api_key, model, provider, system_prompt=attempt_system_prompt)
        except Exception as e:
            print(f"ERROR calling LLM: {e}")
            return 1

        repair_errors: list[dict] = []
        repair_shape_valid: bool | None = True
        repair_payload_eligible: bool | None = True
        repair_global_budget_valid: bool | None = True
        repair_scene_targets_met: bool | None = True
        repair_scene_target_deviations: list[dict] = []
        repair_proposed_word_count: int | None = None
        repair_proposed_scene_word_counts: list[int] | None = None
        repair_proposed_candidate_rank: list[int] | None = None
        candidate_updated = True
        candidate_reused = False
        word_count_source = "generated_candidate"
        if prompt_strategy == "compression":
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = None
            if not isinstance(parsed, dict):
                repair_shape_valid = False
                repair_payload_eligible = False
                repair_global_budget_valid = False
                repair_scene_targets_met = False
                candidate_updated = False
                candidate_reused = True
                word_count_source = "previous_candidate"
                repair_errors = [{"code": "REPAIR_NOT_JSON",
                                  "path": ".", "message": "compression response was not a JSON object"}]
            else:
                expected_nums = list(range(1, len(scene_word_targets) + 1))
                repaired, shape_errors = _apply_voiceover_repair(
                    candidate_script, parsed, expected_scene_numbers=expected_nums,
                )
                repair_shape_valid = not shape_errors
                repair_errors = shape_errors
                if repaired is None:
                    repair_payload_eligible = False
                    repair_global_budget_valid = False
                    repair_scene_targets_met = False
                    candidate_updated = False
                    candidate_reused = True
                    word_count_source = "previous_candidate"
                else:
                    repair_payload_eligible = True
                    proposed_canonical, proposed_v2_errs, _ = _validate_and_canonicalize_script_v2(
                        repaired, allow_generated_images=allow_generated_images,
                    )
                    if proposed_canonical is None:
                        # canonicalization failed: reject the payload, keep active
                        repair_errors = proposed_v2_errs
                        repair_payload_eligible = False
                        repair_global_budget_valid = False
                        repair_scene_targets_met = False
                        candidate_updated = False
                        candidate_reused = True
                        word_count_source = "previous_candidate"
                    else:
                        proposed_word_count = _count_voiceover_words(proposed_canonical)
                        proposed_scene_counts = _scene_word_counts(proposed_canonical)
                        proposed_candidate_rank = _candidate_rank(proposed_word_count, retry_budget)
                        proposed_global_valid = (
                            retry_budget["minimumWords"] <= proposed_word_count <= retry_budget["maximumWords"]
                        )
                        proposed_targets_met, proposed_deviations = _evaluate_scene_word_targets(
                            proposed_scene_counts, scene_word_targets,
                        )
                        repair_proposed_word_count = proposed_word_count
                        repair_proposed_scene_word_counts = proposed_scene_counts
                        repair_proposed_candidate_rank = [proposed_candidate_rank[0], proposed_candidate_rank[1]]
                        repair_global_budget_valid = proposed_global_valid
                        repair_scene_targets_met = proposed_targets_met
                        repair_scene_target_deviations = proposed_deviations
                        if proposed_global_valid:
                            # PASS global: accept immediately; scene targets are guidance.
                            script_data = proposed_canonical
                            candidate_updated = True
                            candidate_reused = False
                            word_count_source = "repaired_candidate"
                        elif active_candidate_rank is not None and proposed_candidate_rank < active_candidate_rank:
                            # Improves the active candidate (monotonic convergence).
                            script_data = proposed_canonical
                            candidate_updated = True
                            candidate_reused = False
                            word_count_source = "repaired_candidate"
                        else:
                            # Tie or regression: keep the previous active candidate.
                            candidate_updated = False
                            candidate_reused = True
                            word_count_source = "previous_candidate"
        else:
            try:
                script_data = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"ERROR parsing LLM response as JSON: {e}")
                print(f"Raw response: {content[:500]}")
                return 1
            candidate_updated = True
            candidate_reused = False
            word_count_source = "generated_candidate"

        word_count = _count_voiceover_words(script_data)
        scene_count = len(script_data.get("scenes", []))
        estimated_dur, spoken_sec, pause_sec = _estimate_narration_duration_sec(word_count, scene_count)

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

        # ── Duration check ──────────────────────────────────────────
        if strictness == "strict":
            margin = target_dur * 0.10
            duration_ok = (target_dur - margin) <= estimated_dur <= (target_dur + margin)
        elif strictness == "balanced":
            duration_ok = min_sec <= estimated_dur <= max_sec
        else:
            duration_ok = True

        # ── V2 validation ───────────────────────────────────────
        canonical, v2_errs, _ = _validate_and_canonicalize_script_v2(
            script_data, allow_generated_images=allow_generated_images,
        )
        v2_structural_issues = v2_errs
        v2_valid = canonical is not None

        if not v2_valid:
            retry_reason = v2_errs[0]["code"] if v2_errs else "invalid_v2_structure"
            retry_instruction = "fix_v2_structure_then_duration"
        elif duration_ok:
            retry_reason = "in_range"
            retry_instruction = "none_needed"
        elif word_count < final_budget["minimumWords"]:
            retry_reason = "below_minimum_words"
            retry_instruction = "expand_content"
        elif word_count > final_budget["maximumWords"]:
            retry_reason = "above_maximum_words"
            retry_instruction = "reduce_content"
        else:
            retry_reason = "duration_out_of_range"
            retry_instruction = "expand_content"

        distance = _distance_to_allowed_range(word_count, final_budget)
        scene_word_counts = _scene_word_counts(script_data)
        duration_status = "PASS" if duration_ok else "FAIL"
        candidate_rank = _candidate_rank(word_count, final_budget)

        retry_entry: dict = {
            "retry": retries,
            "attempt": retries,
            "strategy": prompt_strategy,
            "reason": retry_reason,
            "actualWordCount": word_count,
            "wordCount": word_count,
            "minimumWords": final_budget["minimumWords"],
            "preferredWords": final_budget["preferredWords"],
            "maximumWords": final_budget["maximumWords"],
            "estimatedDurationSec": round(estimated_dur, 1),
            "instructionType": retry_instruction,
            "structureValid": v2_valid,
            "durationStatus": duration_status,
            "sceneWordCounts": scene_word_counts,
            "distanceToAllowedRange": distance,
            "candidateUpdated": candidate_updated,
            "candidateReused": candidate_reused,
            "candidateRank": [candidate_rank[0], candidate_rank[1]],
            "wordCountSource": word_count_source,
            "becameBestCandidate": False,
            "acceptedAsBest": False,
        }
        if prompt_strategy == "compression":
            retry_entry.update({
                "sceneWordTargets": scene_word_targets_entry,
                "targetReductionWords": target_reduction_words,
                "repairShapeValid": repair_shape_valid,
                "repairPayloadEligible": repair_payload_eligible,
                "repairGlobalBudgetValid": repair_global_budget_valid,
                "repairSceneTargetsMet": repair_scene_targets_met,
                "repairSceneTargetDeviations": repair_scene_target_deviations,
                "repairProposedWordCount": repair_proposed_word_count,
                "repairProposedSceneWordCounts": repair_proposed_scene_word_counts,
                "repairProposedCandidateRank": repair_proposed_candidate_rank,
                "repairPayloadValid": repair_payload_eligible,
                "repairBudgetValid": repair_global_budget_valid,
                "sceneWordCaps": scene_word_targets_entry,
                "sceneWordCapsEnforced": False,
                "sceneWordCapsDeprecated": True,
            })
            if not repair_payload_eligible:
                retry_entry["repairErrors"] = repair_errors
        else:
            retry_entry.update({
                "sceneWordTargets": None,
                "targetReductionWords": None,
                "repairShapeValid": None,
                "repairPayloadEligible": None,
                "repairGlobalBudgetValid": None,
                "repairSceneTargetsMet": None,
                "repairSceneTargetDeviations": None,
                "repairProposedWordCount": None,
                "repairProposedSceneWordCounts": None,
                "repairProposedCandidateRank": None,
                "repairPayloadValid": None,
                "repairBudgetValid": None,
                "sceneWordCaps": None,
            })
        if not v2_valid:
            retry_entry["structuralIssues"] = _count_v2_structural_issue_codes(v2_errs)
            retry_entry["structuralIssueDetails"] = _count_v2_structural_issue_messages(v2_errs)
        retry_history.append(retry_entry)

        # ── Best structurally-valid candidate (canonical) ──────────
        if v2_valid:
            candidate_script = canonical
            if best_candidate is None or candidate_rank < best_candidate_rank:
                best_candidate = copy.deepcopy(candidate_script)
                best_word_count = word_count
                best_attempt_idx = retries
                best_distance = distance
                best_scene_word_counts = scene_word_counts
                best_candidate_rank = candidate_rank
                retry_entry["becameBestCandidate"] = True

        if v2_valid and duration_ok:
            script_data = canonical
            best_candidate = copy.deepcopy(canonical)
            best_word_count = word_count
            best_attempt_idx = retries
            best_distance = distance
            best_scene_word_counts = scene_word_counts
            best_candidate_rank = candidate_rank
            print(f"  Accepted v2: canonical valid + duration OK ({estimated_dur:.1f}s within range)")
            break

        retries += 1

    # ── acceptedAsBest: single unambiguous best ───────────────────
    for entry in retry_history:
        entry["acceptedAsBest"] = False
    if best_attempt_idx is not None:
        for entry in retry_history:
            if entry["attempt"] == best_attempt_idx:
                entry["acceptedAsBest"] = True
                break

    # ── Best candidate on exhaustion without PASS ───────────────────
    last_attempt_discarded_as_regression = False
    if retries >= MAX_SCRIPT_ATTEMPTS and best_candidate is not None:
        last_entry = retry_history[-1] if retry_history else None
        if last_entry is not None and best_candidate_rank is not None:
            # A compression payload that was eligible (shape-valid and evaluated)
            # but failed to update the active candidate is a regression candidate;
            # a shape-invalid payload never became a candidate and is not flagged.
            if last_entry.get("strategy") == "compression":
                # A compression payload that was eligible (shape-valid and
                # evaluated) but failed to update the active candidate is a
                # regression; compare its proposed rank against the best.
                is_last_new_valid_candidate = last_entry.get("repairPayloadEligible") is True
                proposed_rank = last_entry.get("repairProposedCandidateRank")
                last_rank = tuple(proposed_rank) if proposed_rank else None
            else:
                is_last_new_valid_candidate = bool(
                    last_entry.get("candidateUpdated") and last_entry.get("structureValid")
                )
                last_rank = last_entry.get("candidateRank")
            if is_last_new_valid_candidate and last_rank is not None:
                last_rank_t = tuple(last_rank)
                if (
                    last_rank_t > best_candidate_rank
                    and best_attempt_idx is not None
                    and best_attempt_idx != (len(retry_history) - 1)
                ):
                    last_attempt_discarded_as_regression = True
        script_data = best_candidate
        best_word_count = best_word_count if best_word_count is not None else _count_voiceover_words(script_data)
        best_scene_word_counts = best_scene_word_counts if best_scene_word_counts is not None else _scene_word_counts(script_data)

    job_id = generate_job_id(args.topic)

    # ── Build request ────────────────────────────────────────────────
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

    visuals_request = {
        "mode": "images",
        "allowGeneratedImages": allow_generated_images,
    }
    visuals_request["schemaVersion"] = 2

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
        "visuals": visuals_request,
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

    # Recompute the budget for the persisted script's scene count so the
    # durationContract stays consistent when the best candidate is selected
    # (it may differ from the last loop iteration's scene count).
    final_budget = calculate_word_budget(
        target_sec=target_dur,
        min_sec=min_sec,
        max_sec=max_sec,
        spoken_words_per_minute=SPOKEN_WORDS_PER_MINUTE,
        scene_count=scene_count,
        estimated_scene_pause_ms=ESTIMATED_SCENE_PAUSE_MS,
    )

    # ── Final determination ──────────────────────────────────────────
    duration_ok_after_retries = False
    if strictness == "strict":
        margin = target_dur * 0.10
        duration_ok_after_retries = (target_dur - margin) <= estimated_dur <= (target_dur + margin)
    elif strictness == "balanced":
        duration_ok_after_retries = min_sec <= estimated_dur <= max_sec
    else:
        duration_ok_after_retries = True

    review_reasons = []
    structure_valid_after_retries = True
    structure_issue_codes: list[str] = []

    canonical, v2_errs, _ = _validate_and_canonicalize_script_v2(
        script_data, allow_generated_images=allow_generated_images,
    )
    v2_valid = canonical is not None
    if not v2_valid:
        structure_valid_after_retries = False
        structure_issue_codes = _count_v2_structural_issue_codes(v2_errs)
        for issue in v2_errs:
            review_reasons.append(f"V2_STRUCTURE_{issue.get('code', 'UNKNOWN')}: {issue.get('message', '')}")

    if not duration_ok_after_retries:
        review_reasons.append(
            f"DURATION_OUT_OF_RANGE: estimated={estimated_dur:.1f}s "
            f"(spoken={spoken_sec:.1f}s + pauses={pause_sec:.1f}s), "
            f"target={target_dur}s, min={min_sec}s, max={max_sec}s, "
            f"words={word_count}, scenes={scene_count}"
        )

    all_ok = duration_ok_after_retries and structure_valid_after_retries
    status = "SCRIPT_DRAFT" if all_ok else "REVIEW_REQUIRED"

    # For REVIEW_REQUIRED after exhausted retries, add explicit reason
    if not all_ok and retries >= MAX_SCRIPT_ATTEMPTS:
        if not structure_valid_after_retries:
            review_reasons.insert(0, "VISUAL_PLAN_V2_INVALID: v2 plan validation failed after 3 attempts")

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

    # Use canonical script whenever the structure is valid (canonical is the
    # contract representation; it must be persisted even when duration fails).
    script_to_persist = script_data
    canonical_final, _, _ = _validate_and_canonicalize_script_v2(
        script_data, allow_generated_images=allow_generated_images,
    )
    if canonical_final is not None:
        script_to_persist = canonical_final

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
        "script": script_to_persist,
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
            "structureValid": structure_valid_after_retries,
            "structureIssues": structure_issue_codes,
            "bestAttempt": best_attempt_idx,
            "bestAttemptWordCount": best_word_count,
            "lastAttemptDiscardedAsRegression": last_attempt_discarded_as_regression,
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
    save_metadata(str(out_path), metadata)

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
        "visualSchemaVersion": 2,
        "status": status,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
