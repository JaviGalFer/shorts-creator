#!/usr/bin/env python3

import argparse
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
from visual_plan_v2 import canonicalize_visual_plan_v2

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
| `assetPreferences` | string[] | Tipos de asset preferidos para esta escena. No vacío. Valores: diagram, illustration, photograph, painting, archive, map, document, stock |
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

### AssetPreferences permitidos

- `diagram`: Diagramas, esquemas, infografías
- `illustration`: Ilustraciones, dibujos artísticos
- `photograph`: Fotografías
- `painting`: Pinturas, obras de arte
- `archive`: Material de archivo histórico
- `map`: Mapas, cartografía
- `document`: Documentos, cartas, periódicos
- `stock`: Imágenes de stock genéricas

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


def _build_user_prompt_v2(topic: str, budget: dict, strictness: str) -> str:
    """Build the v2 user prompt — neutral, no historical domain requirements."""
    duration_instruction = _build_duration_prompt_instruction_v2(budget, strictness)
    return (
        f"Genera un guion divulgativo muy atractivo para vídeo vertical sobre: {topic}. "
        f"Quiero que el arranque tenga máxima retención, que cada escena tenga un plan visual detallado "
        f"con visualPlan schema v2, y que la progresión visual sea coherente. "
        f"IMPORTANTE: Cada escena DEBE tener un visualPlan completo con _schemaVersion=2, "
        f"visualIntent, subjects, searchQueries, assetPreferences y visualSequence.\n\n"
        f"{duration_instruction}"
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


def _build_retry_instruction_v2(
    budget: dict,
    actual_word_count: int,
    actual_scene_count: int,
    estimated_dur: float,
    structural_issues: list[dict],
    allow_generated_images: bool,
) -> str:
    """Build v2-specific retry instruction with per-scene error details."""
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

    # Structural issues
    if structural_issues:
        lines.append("### Problemas estructurales que debes corregir:")
        lines.append("")
        by_scene: dict[int, list[dict]] = {}
        for issue in structural_issues:
            sn = issue.get("sceneNumber")
            if sn is not None:
                by_scene.setdefault(sn, []).append(issue)
            else:
                lines.append(f"- [{issue.get('code', 'UNKNOWN')}] {issue.get('message', '')}")

        for sn in sorted(by_scene.keys()):
            lines.append(f"**Escena {sn}:**")
            for issue in by_scene[sn]:
                lines.append(f"  - [{issue.get('code', 'UNKNOWN')}] {issue.get('message', '')}")
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
        if not allow_generated_images:
            lines.append("- NO uses 'generated' como assetPreference. allowGeneratedImage es false.")
        lines.append("")

    # Duration correction
    lines.append("### Contrato de duración:")
    lines.append(f"- Duración: {dur_target}s objetivo, ventana {dur_min}-{dur_max}s")
    lines.append(f"- Palabras totales: mínimo {min_w}, preferidas ~{pref_w}, máximo {max_w}")
    lines.append(f"- Pausas entre escenas: ~{pause_ms}ms cada una")

    if missing > 0:
        lines.append("")
        lines.append(
            f"El guion se queda corto por aproximadamente {missing} palabras. "
            f"Añade entre {missing} y {missing + 5} palabras "
            f"significativas distribuidas naturalmente entre las escenas existentes."
        )
    elif excess > 0:
        lines.append("")
        lines.append(
            f"El guion excede por aproximadamente {excess} palabras. "
            f"Reduce aproximadamente {excess} palabras del contenido."
        )

    lines.append("")
    lines.append("### Reglas obligatorias:")
    lines.append("- DEBEN SER ENTRE 4 Y 6 ESCENAS. Mínimo 4, máximo 6. Prefiere 5.")
    lines.append("- El CTA debe estar DENTRO de la última escena, nunca como escena aparte.")
    lines.append("- Cada escena debe tener al menos 7 palabras de voiceover.")
    lines.append("- Cada escena DEBE tener visualPlan v2 completo con _schemaVersion=2.")
    lines.append("- No incluyas campos prohibidos en visualPlan.")
    lines.append("- No incluyas campos desconocidos en visualPlan ni en segmentos.")
    lines.append("- Responde SOLO con JSON válido, sin markdown ni explicaciones.")

    return "\n".join(lines)


# ── Legacy count helpers for v2 retry stats ──────────────────────────

def _count_v2_structural_issue_codes(issues: list[dict]) -> list[str]:
    return [i.get("code", "UNKNOWN") for i in issues]


def _count_v2_structural_issue_messages(issues: list[dict]) -> list[str]:
    return [i.get("message", "") for i in issues]


# ── main ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True, help="Topic for the video")
    parser.add_argument("--output", help="Output path for metadata.json (default: data/videos/{jobId}/metadata.json)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt and exit without calling API")
    parser.add_argument("--model", help="LLM model override")
    parser.add_argument("--visual-schema-version", type=int, choices=[2], default=2,
                        help="VisualPlan schema version (only V2 supported)")
    add_duration_profile_args(parser)
    args = parser.parse_args()

    visual_schema_version = args.visual_schema_version

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
    base_prompt = _build_user_prompt_v2(args.topic, provisional_budget, strictness)

    if args.dry_run:
        print("=== SYSTEM PROMPT ===")
        print(active_system_prompt)
        print("\n=== USER PROMPT ===")
        print(base_prompt)
        print("\n=== MODEL ===")
        print(f"provider={provider}, model={model}")
        print(f"visualSchemaVersion={visual_schema_version}")
        return 0

    print(f"Generating script for topic: {args.topic}")
    print(f"Using model: {model} ({provider})")
    print(f"Visual schema version: {visual_schema_version}")
    print(f"Duration target: {target_dur}s, min: {min_sec}s, max: {max_sec}s, strictness: {strictness}")

    # ── Retry loop ────────────────────────────────────────────────────
    script_data: dict = {}
    retries = 0
    retry_history: list[dict] = []
    current_prompt = base_prompt
    final_budget = dict(provisional_budget)
    v2_structural_issues: list[dict] = []

    allow_generated_images = False  # default for request

    while retries < MAX_SCRIPT_ATTEMPTS:
        if retries > 0:
            word_count = _count_voiceover_words(script_data)
            scene_count = len(script_data.get("scenes", []))
            estimated_dur, _, _ = _estimate_narration_duration_sec(word_count, scene_count)
            retry_budget = calculate_word_budget(
                target_sec=target_dur,
                min_sec=min_sec,
                max_sec=max_sec,
                spoken_words_per_minute=SPOKEN_WORDS_PER_MINUTE,
                scene_count=scene_count if scene_count >= MIN_SCENE_COUNT else PROVISIONAL_SCENE_COUNT,
                estimated_scene_pause_ms=ESTIMATED_SCENE_PAUSE_MS,
            )

            # V2 structural validation
            canonical, v2_errs, _ = _validate_and_canonicalize_script_v2(
                script_data, allow_generated_images=allow_generated_images,
            )
            v2_structural_issues = v2_errs
            v2_valid = canonical is not None

            retry_inst = _build_retry_instruction_v2(
                retry_budget, word_count, scene_count, estimated_dur,
                structural_issues=v2_errs if not v2_valid else [],
                allow_generated_images=allow_generated_images,
            )
            base_retry = _build_user_prompt_v2(args.topic, retry_budget, strictness)
            current_prompt = f"{base_retry}\n\n---\n{retry_inst}"
            print(f"Retry {retries}/{MAX_SCRIPT_ATTEMPTS - 1}: generated {word_count} words, "
                  f"estimated {estimated_dur:.1f}s, "
                  f"v2 valid={v2_valid}, errors={len(v2_errs)}")

        try:
            content = call_llm(current_prompt, api_key, model, provider, system_prompt=SYSTEM_PROMPT_V2)
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

        retry_entry: dict = {
            "retry": retries,
            "reason": retry_reason,
            "actualWordCount": word_count,
            "minimumWords": final_budget["minimumWords"],
            "preferredWords": final_budget["preferredWords"],
            "maximumWords": final_budget["maximumWords"],
            "estimatedDurationSec": round(estimated_dur, 1),
            "instructionType": retry_instruction,
        }
        if not v2_valid:
            retry_entry["structuralIssues"] = _count_v2_structural_issue_codes(v2_errs)
            retry_entry["structuralIssueDetails"] = _count_v2_structural_issue_messages(v2_errs)
        retry_history.append(retry_entry)

        if v2_valid and duration_ok:
            script_data = canonical
            print(f"  Accepted v2: canonical valid + duration OK ({estimated_dur:.1f}s within range)")
            break

        retries += 1

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
        "allowGeneratedImages": False,
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

    # Use canonical script if available
    script_to_persist = script_data
    if all_ok:
        canonical, _, _ = _validate_and_canonicalize_script_v2(
            script_data, allow_generated_images=allow_generated_images,
        )
        if canonical is not None:
            script_to_persist = canonical

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
        "visualSchemaVersion": visual_schema_version,
        "status": status,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
