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

from duration_profiles import add_duration_profile_args, resolve_requested_duration, calculate_word_budget
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
MIN_WORDS_PER_SCENE = 7


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
ni ningún otro campo."""


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


def call_llm(prompt: str, api_key: str, model: str, provider: str = "openai", system_prompt: str | None = None) -> str:
    sp = system_prompt if system_prompt is not None else SYSTEM_PROMPT_V2
    if provider == "openai":
        data = json.dumps({
            "model": model,
            "response_format": {"type": "json_object"},
            "temperature": 0.8,
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
    lines.append(f"- NO uses frases de relleno, CTA repetido, oraciones duplicadas ni pausas dramáticas falsas.")
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


def _allocate_scene_word_caps(maximum_words: int, scene_count: int) -> list[int]:
    """Deterministically distribute a global max word budget across scenes.

    Contract:
    * scene_count > 0;
    * length equals scene_count;
    * every cap is a positive integer;
    * sum exactly equals maximum_words;
    * max - min <= 1;
    * deterministic distribution.

    Example: maximum_words=52, scene_count=5 -> [11, 11, 10, 10, 10].
    """
    if scene_count <= 0:
        raise ValueError("scene_count must be > 0")
    if maximum_words < scene_count:
        raise ValueError("maximum_words must be >= scene_count")
    base = maximum_words // scene_count
    remainder = maximum_words % scene_count
    caps = [base + 1] * remainder + [base] * (scene_count - remainder)
    return caps


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
    scene_word_caps: list[int],
    *,
    allow_generated_images: bool,
) -> str:
    """Build the specialized voiceover-only compression prompt.

    Used when the previous attempt is structurally valid but exceeds the
    maximum word budget. The model compresses the existing voiceovers only —
    it never regenerates the full script or the visual plan.
    """
    min_w = budget.get("minimumWords", 0)
    pref_w = budget.get("preferredWords", 0)
    max_w = budget.get("maximumWords", 0)
    scenes = canonical_script.get("scenes", [])
    expected = list(range(1, len(scene_word_caps) + 1))

    lines = [
        "## Compresión de voz en off — intento anterior excede la duración",
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
            "scenes": [
                {
                    "sceneNumber": scenes[i]["sceneNumber"],
                    "currentVoiceover": scenes[i].get("voiceover", ""),
                    "maximumWords": scene_word_caps[i],
                }
                for i in range(len(scenes))
            ]
        }, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Reglas de compresión",
        "",
        "- Comprime cada voiceover para que NO supere su `maximumWords` de esa escena.",
        f"- Presupuesto global: mínimo {min_w}, preferido ~{pref_w}, máximo {max_w} palabras en total.",
        f"- El total reparado DEBE quedar dentro de [{min_w}, {max_w}] palabras.",
        "- No superes NINGÚN cap individual por escena.",
        "- Conserva el número de escenas y cada `sceneNumber` exactamente.",
        "- No cambies el plan visual ni ningún otro campo del guion.",
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
        "- Revisa que cada voiceover esté dentro de su cap de `maximumWords`.",
        "- Revisa que la suma total esté dentro de [{min_w}, {max_w}].",
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
    scene_word_caps: list[int],
) -> tuple[dict | None, list[dict], list[dict]]:
    """Merge a voiceover-only repair payload into a deep copy of base_script.

    Accepts only:
        {"scenes": [{"sceneNumber": 1, "voiceover": "..."}]}

    Returns (merged_script | None, shape_errors, budget_errors).

    * shape_errors cover structural validity (object shape, scene list, item
      fields, sceneNumber type/sequence, voiceover string/non-empty).
    * budget_errors cover per-scene word budgets:
        MIN_WORDS_PER_SCENE <= wordCount <= sceneWordCap

    The merge is applied ONLY when both shape and budget are valid; otherwise
    base_script is never mutated and no partial merge happens. scene_word_caps
    is indexed by sceneNumber (cap for scene i+1 is scene_word_caps[i]).
    """
    shape_errors: list[dict] = []
    budget_errors: list[dict] = []

    expected = list(expected_scene_numbers)

    # ── Cap contract validation ─────────────────────────────────────────
    if (
        not isinstance(scene_word_caps, list)
        or len(scene_word_caps) != len(expected)
        or any(
            not isinstance(c, int) or isinstance(c, bool) or c < MIN_WORDS_PER_SCENE
            for c in scene_word_caps
        )
    ):
        budget_errors.append({
            "sceneNumber": None,
            "code": "REPAIR_INVALID_SCENE_CAPS",
            "path": "scenes",
            "message": (
                f"scene_word_caps must be a list of {len(expected)} integers, "
                f"each >= {MIN_WORDS_PER_SCENE}, got {scene_word_caps!r}"
            ),
        })
        return None, [], budget_errors

    if not isinstance(repair_payload, dict):
        shape_errors.append({"code": "REPAIR_NOT_OBJECT", "path": ".",
                             "message": "repair payload must be a JSON object"})
        return None, shape_errors, []

    top_keys = set(repair_payload.keys())
    if top_keys != {"scenes"}:
        extra = sorted(top_keys - {"scenes"})
        shape_errors.append({"code": "REPAIR_UNEXPECTED_TOP_FIELD", "path": ".",
                             "message": f"unexpected top-level fields: {extra}"})
        return None, shape_errors, []

    payload_scenes = repair_payload.get("scenes")
    if not isinstance(payload_scenes, list):
        shape_errors.append({"code": "REPAIR_SCENES_NOT_LIST", "path": "scenes",
                             "message": "scenes must be a list"})
        return None, shape_errors, []

    seen: set[int] = set()
    for i, item in enumerate(payload_scenes):
        if not isinstance(item, dict):
            shape_errors.append({"sceneNumber": None, "code": "REPAIR_ITEM_NOT_OBJECT",
                                 "path": f"scenes[{i}]", "message": "scene item must be an object"})
            continue
        item_keys = set(item.keys())
        if item_keys != {"sceneNumber", "voiceover"}:
            extra = sorted(item_keys - {"sceneNumber", "voiceover"})
            shape_errors.append({"sceneNumber": item.get("sceneNumber"),
                                 "code": "REPAIR_UNEXPECTED_FIELD",
                                 "path": f"scenes[{i}]",
                                 "message": f"unexpected fields: {extra}"})
        sn = item.get("sceneNumber")
        if not isinstance(sn, int) or isinstance(sn, bool):
            shape_errors.append({"sceneNumber": sn, "code": "REPAIR_BAD_SCENE_NUMBER",
                                 "path": f"scenes[{i}].sceneNumber",
                                 "message": "sceneNumber must be an int"})
            continue
        if sn in seen:
            shape_errors.append({"sceneNumber": sn, "code": "REPAIR_DUPLICATE_SCENE",
                                 "path": f"scenes[{i}].sceneNumber",
                                 "message": f"duplicate sceneNumber {sn}"})
        seen.add(sn)
        vo = item.get("voiceover")
        if not isinstance(vo, str):
            shape_errors.append({"sceneNumber": sn, "code": "REPAIR_VOICEOVER_NOT_STRING",
                                 "path": f"scenes[{i}].voiceover",
                                 "message": "voiceover must be a string"})
        elif not vo.strip():
            shape_errors.append({"sceneNumber": sn, "code": "REPAIR_VOICEOVER_EMPTY",
                                 "path": f"scenes[{i}].voiceover",
                                 "message": "voiceover cannot be empty"})

    if shape_errors:
        return None, shape_errors, []

    got_numbers = [item["sceneNumber"] for item in payload_scenes]
    if got_numbers != expected:
        shape_errors.append({"sceneNumber": None, "code": "REPAIR_SCENE_SEQUENCE",
                             "path": "scenes",
                             "message": f"expected sceneNumber {expected}, got {got_numbers}"})
        return None, shape_errors, []

    # ── Per-scene word budget enforcement ───────────────────────────────
    for i, item in enumerate(payload_scenes):
        sn = item["sceneNumber"]
        cap = scene_word_caps[i]
        wc = len((item.get("voiceover") or "").split())
        if wc < MIN_WORDS_PER_SCENE:
            budget_errors.append({
                "sceneNumber": sn,
                "code": "REPAIR_SCENE_WORD_MINIMUM_NOT_MET",
                "path": f"scenes[{i}].voiceover",
                "message": f"scene {sn}: voiceover has {wc} words, below the minimum {MIN_WORDS_PER_SCENE}",
            })
        elif wc > cap:
            budget_errors.append({
                "sceneNumber": sn,
                "code": "REPAIR_SCENE_WORD_CAP_EXCEEDED",
                "path": f"scenes[{i}].voiceover",
                "message": f"scene {sn}: voiceover has {wc} words, exceeding cap {cap}",
            })

    if budget_errors:
        return None, [], budget_errors

    merged = copy.deepcopy(base_script)
    by_number = {item["sceneNumber"]: item["voiceover"] for item in payload_scenes}
    for scene in merged.get("scenes", []):
        sn = scene.get("sceneNumber")
        if sn in by_number:
            scene["voiceover"] = by_number[sn]
    return merged, [], []


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
        scene_caps: list[int] | None = None

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
                scene_caps = _allocate_scene_word_caps(retry_budget["maximumWords"], scene_count)
                current_prompt = _build_voiceover_compression_prompt(
                    candidate_script, retry_budget, word_count, scene_caps,
                    allow_generated_images=allow_generated_images,
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

        repair_payload_valid = True
        repair_shape_valid = True
        repair_budget_valid = True
        repair_errors: list[dict] = []
        candidate_updated = True
        candidate_reused = False
        word_count_source = "generated_candidate"
        if prompt_strategy == "compression":
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = None
            if not isinstance(parsed, dict):
                repair_payload_valid = False
                repair_shape_valid = False
                candidate_updated = False
                candidate_reused = True
                word_count_source = "previous_candidate"
                repair_errors = [{"code": "REPAIR_NOT_JSON",
                                  "path": ".", "message": "compression response was not a JSON object"}]
            else:
                expected_nums = list(range(1, len(scene_caps) + 1))
                repaired, shape_errors, budget_errors = _apply_voiceover_repair(
                    candidate_script, parsed, expected_scene_numbers=expected_nums,
                    scene_word_caps=scene_caps,
                )
                repair_shape_valid = not shape_errors
                repair_budget_valid = not budget_errors
                repair_payload_valid = repair_shape_valid and repair_budget_valid
                repair_errors = shape_errors + budget_errors
                if repaired is not None:
                    script_data = repaired
                    candidate_updated = True
                    candidate_reused = False
                    word_count_source = "repaired_candidate"
                else:
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
            "sceneWordCaps": scene_caps,
            "distanceToAllowedRange": distance,
            "candidateUpdated": candidate_updated,
            "candidateReused": candidate_reused,
            "candidateRank": [candidate_rank[0], candidate_rank[1]],
            "wordCountSource": word_count_source,
            "repairShapeValid": repair_shape_valid,
            "repairBudgetValid": repair_budget_valid,
            "repairPayloadValid": repair_payload_valid,
            "becameBestCandidate": False,
            "acceptedAsBest": False,
        }
        if not v2_valid:
            retry_entry["structuralIssues"] = _count_v2_structural_issue_codes(v2_errs)
            retry_entry["structuralIssueDetails"] = _count_v2_structural_issue_messages(v2_errs)
        if not repair_payload_valid:
            retry_entry["repairErrors"] = repair_errors
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
            is_last_new_valid_candidate = (
                last_entry.get("candidateUpdated")
                and last_entry.get("structureValid")
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
        "visualSchemaVersion": 2,
        "status": status,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
