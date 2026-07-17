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
from editorial_asset_contract import is_asset_type_allowed, is_temporal_intent_allowed, allowed_asset_types_for_role
import editorial_asset_contract
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
- Escenas ≤4s: EXACTAMENTE 1 segmento (sin división)
- Escenas 5-7s: EXACTAMENTE 2 segmentos, cada uno con durationFraction (la suma debe ser 1.0)
- Escenas ≥8s: 2-3 segmentos, cada uno con durationFraction (la suma debe ser 1.0)
- Toda escena >4s DEBE tener al menos 2 segmentos en visualSequence. Es una regla técnica obligatoria.
- No repetir assetType en segmentos consecutivos de la misma escena
- No repetir generated_reconstruction en escenas consecutivas
- generated_reconstruction: máximo 1 por escena
- historical_map: ideal como segmento inicial para contexto espacial
- Para document y map: durationFraction mayor para que se vea bien

### Reglas de composición:
- Si el assetType es historical_map o document, indicar en editorialReason si necesita centrado o zoom a región
- Para portrait, debe acompañarse de painting, historical_photograph o historical_art (nunca atmospheric_broll ni broll)
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

## Cheat sheet: tipos de asset permitidos por rol editorial

| editorialRole | Asset types permitidos |
|---------------|----------------------|
| context_map | map, historical_map, document, newspaper |
| document_or_date | document, newspaper, map, historical_map |
| character_portrait | portrait, historical_photograph, painting, historical_art |
| military_technology | historical_photograph, painting, document, historical_art |
| civilian_impact | historical_photograph, historical_art, historical_art |
| battle_or_assault | historical_photograph, historical_art, painting |
| border_closure_construction | historical_photograph, historical_art, painting |
| consequence_or_legacy (event_depiction) | historical_photograph, historical_art, painting |
| consequence_or_legacy (legacy_or_commemoration) | historical_photograph, historical_art, painting, atmospheric_broll, broll |
| atmospheric_transition | atmospheric_broll, broll, historical_photograph, painting |

El broll solo está permitido en consequence_or_legacy con legacy_or_commemoration y en atmospheric_transition. Para cualquier otro rol, usar historical_photograph, historical_art, painting, document, map, historical_map u otros tipos documentales según la tabla.

## Relación obligatoria editorialRole ↔ visualTemporalIntent

| editorialRole | visualTemporalIntent |
|---------------|---------------------|
| context_map, character_portrait, battle_or_assault, military_technology, civilian_impact, document_or_date, border_closure_construction | SOLO event_depiction |
| consequence_or_legacy | event_depiction O legacy_or_commemoration (según voiceover describa el evento o su legado) |
| atmospheric_transition | SOLO context_or_setup |

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
- B-roll (solo consequence_or_legacy con legacy_or_commemoration): static, slow_zoom_in (suave, no exagerado).
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
        "primaryAssetType": "historical_photograph|map|painting|document|historical_map|historical_art|portrait|newspaper|atmospheric_broll|broll (must be compatible with editorialRole — see cheat sheet below)",
        "secondaryAssetType": "map|document|portrait|historical_photograph|historical_art|null (must be compatible with editorialRole)",
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
            "assetType": "document",
            "searchQuery": "siege of Constantinople 1453 document",
            "durationFraction": 0.5,
            "transition": "fade",
            "editorialReason": "Documento histórico que complementa el mapa de la batalla",
            "motionType": "pan_right"
          }
        ]
      }
    }
  ]
}"""


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
    sp = system_prompt if system_prompt is not None else SYSTEM_PROMPT
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


def _validate_script_structure(script_data: dict, min_scenes: int, topic: str) -> dict:
    """Validate structural completeness of a generated script.

    Returns {valid: bool, reasons: [(code, message), ...]}.
    Duration is checked separately by the budget loop.
    """
    reasons: list[tuple[str, str]] = []
    scenes = script_data.get("scenes", [])

    if not scenes:
        reasons.append(("empty_scenes", "script has no scenes"))
        return {"valid": False, "reasons": reasons}

    if len(scenes) < min_scenes:
        reasons.append(("insufficient_scene_count",
                        f"{len(scenes)} scenes, need at least {min_scenes}"))

    scene_nums = []
    for s in scenes:
        sn = s.get("sceneNumber")
        if isinstance(sn, (int, float)):
            scene_nums.append(int(sn))
        else:
            scene_nums.append(sn)
        vo = (s.get("voiceover") or "").strip()
        if not vo:
            reasons.append(("empty_voiceover",
                            f"scene {sn} has empty voiceover"))
        vp = s.get("visualPlan")
        vti = s.get("visualTemporalIntent", "")
        if not vp or not isinstance(vp, dict):
            reasons.append(("missing_visualPlan",
                            f"scene {sn} missing visualPlan"))
        else:
            er = vp.get("editorialRole", "")
            # Temporal intent compatibility
            if er and vti and not is_temporal_intent_allowed(er, vti):
                allowed_intents = ", ".join(sorted(editorial_asset_contract.ROLE_INTENT_RULES.get(er, set())))
                reasons.append(("forbidden_visual_temporal_intent",
                                f"scene {sn} editorialRole={er} forbids visualTemporalIntent={vti} (allowed: {allowed_intents})"))
            # Primary asset type compatibility
            primary = vp.get("primaryAssetType", "")
            if primary and er and not is_asset_type_allowed(er, primary, vti):
                repl = editorial_asset_contract.suggest_replacement_types(er, primary, vti)
                repl_hint = f" (use: {', '.join(repl[:3])})" if repl else ""
                reasons.append(("forbidden_primary_asset_type",
                                f"scene {sn} editorialRole={er} forbids primaryAssetType={primary}{repl_hint}"))
            # Secondary asset type compatibility
            secondary = vp.get("secondaryAssetType", "")
            if secondary and secondary != "null" and er and not is_asset_type_allowed(er, secondary, vti):
                repl = editorial_asset_contract.suggest_replacement_types(er, secondary, vti)
                repl_hint = f" (use: {', '.join(repl[:3])})" if repl else ""
                reasons.append(("forbidden_secondary_asset_type",
                                f"scene {sn} editorialRole={er} forbids secondaryAssetType={secondary}{repl_hint}"))
            vs = vp.get("visualSequence")
            if not vs or not isinstance(vs, list) or len(vs) == 0:
                reasons.append(("missing_visualSequence",
                                f"scene {sn} missing visualSequence"))
            else:
                dur = s.get("targetDurationSec") or s.get("target_duration_sec") or 0
                seg_count = len(vs)
                if dur <= 4:
                    if seg_count != 1:
                        reasons.append(("invalid_segment_count_short",
                                        f"scene {sn} duration {dur}s requires exactly 1 segment, got {seg_count}"))
                elif dur < 8:
                    if seg_count != 2:
                        reasons.append(("invalid_segment_count_medium",
                                        f"scene {sn} duration {dur}s requires exactly 2 segments, got {seg_count}"))
                else:
                    if seg_count < 2 or seg_count > 3:
                        reasons.append(("invalid_segment_count_long",
                                        f"scene {sn} duration {dur}s requires 2-3 segments, got {seg_count}"))
                for seg in vs:
                    seg_at = seg.get("assetType", "")
                    if seg_at and not is_asset_type_allowed(er, seg_at, vti):
                        repl = editorial_asset_contract.suggest_replacement_types(er, seg_at, vti)
                        repl_hint = f" (use: {', '.join(repl[:3])})" if repl else ""
                        reasons.append(("forbidden_segment_asset_type",
                                        f"scene {sn} editorialRole={er} forbids assetType={seg_at}{repl_hint}"))

    # Scene number order
    numeric_scene_nums = [int(n) for n in scene_nums if isinstance(n, (int, float))]
    if numeric_scene_nums and numeric_scene_nums != sorted(numeric_scene_nums):
        reasons.append(("unordered_scenes", "scene numbers not ordered"))

    # Historical content: at minimum, the script must mention the topic entity
    # or include a proper name, date, or factual claim beyond a generic CTA.
    all_vo = " ".join((s.get("voiceover") or "") for s in scenes)
    has_date = bool(re.search(r'\b(1[89]\d{2}|20\d{2})\b', all_vo))
    has_named_entity = False
    topic_parts = [w for w in re.sub(r'[^a-záéíóúñü ]', '', topic.lower()).split() if len(w) > 2]
    for part in topic_parts:
        if part in all_vo.lower():
            has_named_entity = True
            break
    if not has_named_entity:
        proper_pattern = r'\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+\b'
        if re.search(proper_pattern, all_vo):
            has_named_entity = True
    if not has_date and not has_named_entity:
        reasons.append(("cta_only_or_non_historical",
                        "script lacks factual historical content (no date or named entity)"))

    valid = len(reasons) == 0
    return {"valid": valid, "reasons": reasons}


def _build_retry_instruction(
    budget: dict,
    actual_word_count: int,
    actual_scene_count: int,
    estimated_dur: float,
    structural_issues: list[tuple[str, str]] | None = None,
) -> str:
    min_w = budget.get("minimumWords", 0)
    pref_w = budget.get("preferredWords", 0)
    max_w = budget.get("maximumWords", 0)
    missing = max(0, min_w - actual_word_count)
    excess = max(0, actual_word_count - max_w)
    dur_min = budget.get("minSec", 0)
    dur_max = budget.get("maxSec", 0)
    dur_target = budget.get("targetSec", 0)
    pause_ms = budget.get("estimatedScenePauseMs", 350)

    lines = [
        f"## Corrección de guion — intento anterior insuficiente",
        f"",
        f"El guion anterior tiene {actual_word_count} palabras habladas "
        f"en {actual_scene_count} escenas y estima {estimated_dur:.1f} segundos.",
        f"",
    ]

    # ── Structural issues first ──────────────────────────────────────
    if structural_issues:
        lines.append("### Problemas estructurales que debes corregir:")
        for code, msg in structural_issues:
            lines.append(f"- [{code}] {msg}")
        lines.append("")
        lines.append("Instrucciones para corregir la estructura:")
        lines.append("- El guion debe tener entre 4 y 6 escenas con contenido histórico real.")
        lines.append("- Cada escena DEBE tener voiceover, subtitle, visualPlan y visualSequence.")
        lines.append("- Toda escena de más de 4s DEBE tener EXACTAMENTE 2 segmentos (5-7s) o 2-3 segmentos (≥8s).")
        lines.append("- La duración total de los segmentos (suma de durationFraction) debe ser 1.0.")
        lines.append("- NO hagas un CTA genérico. Cada escena debe aportar contenido histórico con fechas, nombres propios y datos concretos.")
        lines.append("- narrativeBeats y motionType son obligatorios en cada escena.")
        lines.append("")

    # ── Duration correction ─────────────────────────────────────────
    lines.append("### Contrato de duración:")
    lines.append(f"- Duración: {dur_target}s objetivo, ventana {dur_min}-{dur_max}s")
    lines.append(f"- Palabras totales: mínimo {min_w}, preferidas ~{pref_w}, máximo {max_w}")
    lines.append(f"- Pausas entre escenas: ~{pause_ms}ms cada una")

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
    lines.append("### Reglas obligatorias:")
    lines.append("- DEBEN SER ENTRE 4 Y 6 ESCENAS. Mínimo 4, máximo 6. Prefiere 5.")
    lines.append("- El CTA debe estar DENTRO de la última escena, nunca como escena aparte.")
    lines.append("- Cada escena debe tener al menos 7 palabras de voiceover con contenido histórico real.")
    lines.append("- Usa datos concretos: años, cifras, nombres propios.")
    lines.append("- No inventar datos históricos.")
    lines.append("- Incluye al menos una fecha con año y al menos un nombre propio relevante.")
    lines.append("- Toda escena de más de 4s DEBE tener EXACTAMENTE 2 segmentos en visualSequence (5-7s) o 2-3 segmentos (≥8s).")
    lines.append("- Cada segmento debe tener durationFraction; la suma de todas las durationFraction debe ser 1.0.")
    lines.append("- Cada escena DEBE tener visualPlan completo con editorialRole, searchQueries, visualSequence con motionType.")
    lines.append("- Cada escena DEBE tener narrativeBeats.")
    lines.append("- NO crees una escena separada solo para CTA.")
    lines.append("- Responde SOLO con JSON válido, sin markdown ni explicaciones.")

    return "\n".join(lines)


PROVISIONAL_SCENE_COUNT = 5
MIN_SCENE_COUNT = 4
MAX_SCRIPT_ATTEMPTS = 3  # initial generation + up to 2 corrective retries


def _build_user_prompt(topic: str, budget: dict, strictness: str) -> str:
    """Build the complete user prompt with duration instruction and all
    schema/contract requirements. Reused for initial generation and retries."""
    duration_instruction = _build_duration_prompt_instruction(budget, strictness)
    return (
        f"Genera un guion histórico muy atractivo para vídeo vertical sobre: {topic}. "
        f"Quiero que el arranque tenga máxima retención, que cada escena tenga un plan visual detallado "
        f"con visualPlan Y visualSequence, y que la progresión visual sea coherente alternando tipos de "
        f"asset entre escenas. IMPORTANTE: Toda escena de más de 4 segundos DEBE tener 2 o más segmentos "
        f"en visualSequence. También DEBE incluir narrativeBeats array en cada escena y motionType en cada "
        f"segmento de visualSequence. Es una regla técnica obligatoria.\n\n"
        f"{duration_instruction}"
    )


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
    parser.add_argument("--visual-schema-version", type=int, choices=[1, 2], default=2,
                        help="VisualPlan schema version (1=legacy v1, 2=native v2)")
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

    if visual_schema_version == 2:
        active_system_prompt = SYSTEM_PROMPT_V2
        base_prompt = _build_user_prompt_v2(args.topic, provisional_budget, strictness)
    else:
        active_system_prompt = None
        base_prompt = _build_user_prompt(args.topic, provisional_budget, strictness)

    if args.dry_run:
        print("=== SYSTEM PROMPT ===")
        print(active_system_prompt if active_system_prompt else SYSTEM_PROMPT)
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

            if visual_schema_version == 2:
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
            else:
                # V1 structural validation
                sv = _validate_script_structure(script_data, MIN_SCENE_COUNT, args.topic)
                retry_inst = _build_retry_instruction(
                    retry_budget, word_count, scene_count, estimated_dur,
                    structural_issues=sv["reasons"] if not sv["valid"] else None,
                )
                base_retry = _build_user_prompt(args.topic, retry_budget, strictness)
                current_prompt = f"{base_retry}\n\n---\n{retry_inst}"
                print(f"Retry {retries}/{MAX_SCRIPT_ATTEMPTS - 1}: generated {word_count} words, "
                      f"estimated {estimated_dur:.1f}s, need {retry_budget['minimumWords']}-{retry_budget['maximumWords']} words")

        try:
            if visual_schema_version == 2:
                content = call_llm(current_prompt, api_key, model, provider, system_prompt=SYSTEM_PROMPT_V2)
            else:
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

        if visual_schema_version == 2:
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
        else:
            # ── V1 validation ───────────────────────────────────────
            sv = _validate_script_structure(script_data, MIN_SCENE_COUNT, args.topic)

            if not sv["valid"]:
                retry_reason = sv["reasons"][0][0] if sv["reasons"] else "invalid_scene_structure"
                retry_instruction = "fix_structure_then_duration"
            elif duration_ok:
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
            if not sv["valid"]:
                retry_entry["structuralIssues"] = [code for code, _ in sv["reasons"]]
                retry_entry["structuralIssueDetails"] = [msg for _, msg in sv["reasons"]]
            retry_history.append(retry_entry)

            if sv["valid"] and duration_ok:
                print(f"  Accepted: structure valid + duration OK ({estimated_dur:.1f}s within range)")
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
    if visual_schema_version == 2:
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

    if visual_schema_version == 2:
        canonical, v2_errs, _ = _validate_and_canonicalize_script_v2(
            script_data, allow_generated_images=allow_generated_images,
        )
        v2_valid = canonical is not None
        if not v2_valid:
            structure_valid_after_retries = False
            structure_issue_codes = _count_v2_structural_issue_codes(v2_errs)
            for issue in v2_errs:
                review_reasons.append(f"V2_STRUCTURE_{issue.get('code', 'UNKNOWN')}: {issue.get('message', '')}")
    else:
        sv = _validate_script_structure(script_data, MIN_SCENE_COUNT, args.topic)
        if not sv["valid"]:
            structure_valid_after_retries = False
            structure_issue_codes = [code for code, _ in sv["reasons"]]
            for code, msg in sv["reasons"]:
                review_reasons.append(f"STRUCTURE_{code.upper()}: {msg}")

    if not duration_ok_after_retries:
        review_reasons.append(
            f"DURATION_OUT_OF_RANGE: estimated={estimated_dur:.1f}s "
            f"(spoken={spoken_sec:.1f}s + pauses={pause_sec:.1f}s), "
            f"target={target_dur}s, min={min_sec}s, max={max_sec}s, "
            f"words={word_count}, scenes={scene_count}"
        )

    all_ok = duration_ok_after_retries and structure_valid_after_retries
    status = "SCRIPT_DRAFT" if all_ok else "REVIEW_REQUIRED"

    # For v2 REVIEW_REQUIRED after exhausted retries, add explicit reason
    if not all_ok and visual_schema_version == 2 and retries >= MAX_SCRIPT_ATTEMPTS:
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

    # For v2, use canonical script if available
    script_to_persist = script_data
    if visual_schema_version == 2 and all_ok:
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
