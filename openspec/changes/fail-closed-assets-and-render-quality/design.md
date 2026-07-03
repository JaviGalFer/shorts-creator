# Design: Fail-Closed Asset Validation y Calidad Mínima de Render

## Arquitectura

### 1. Asset validation pipeline

```
fetch_images (produce assets con metadata)
    │
    ▼
prepare_job (asigna assets a segmentos)
    │
    ▼
validate_job_for_render(metadata)
    ├── per_segment_validations()
    ├── editorial_coherence_check()
    └── quality_gate()
    │
    ├── PASS → render_job.py proceedes
    ├── REVIEW_REQUIRED → render allowed with warning, status=REVIEW_REQUIRED
    └── BLOCKED → render_job.py aborts, status=ASSET_FAILED
```

### 2. Data model additions

Extend metadata.json with:

```json
{
  "assetValidation": {
    "status": "PASS" | "REVIEW_REQUIRED" | "BLOCKED",
    "failures": [
      {
        "sceneNumber": 1,
        "segmentIndex": 1,
        "rule": "placeholder_detected",
        "message": "Asset contains placeholder text",
        "assetPath": "scenes/scene-01-01.jpg"
      }
    ],
    "perSegment": [
      {
        "sceneNumber": 1,
        "segmentIndex": 1,
        "valid": true,
        "provider": "wikimedia_commons",
        "assetType": "historical_map",
        "editorialRole": "context_map",
        "score": 85,
        "hasPlaceholderText": false,
        "dimensionsOk": true,
        "historicalCoherence": "pass",
        "query": "Map of Constantinople 1453"
      }
    ],
    "summary": {
      "totalSegments": 10,
      "validAssets": 8,
      "invalidAssets": 2,
      "placeholdersDetected": 2,
      "renderBlocked": true,
      "assetsFromArchive": 4,
      "assetsFromBroll": 3,
      "assetsFromAI": 0,
      "scenesRequiringManualReview": 1
    }
  },
  "status": "ASSET_FAILED" | "REVIEW_REQUIRED" | "ASSETS_READY"
}
```

### 3. Rules engine

Each segment is checked against these rule groups:

#### 3a. File-level rules
- `assetPath exists` → file-system check
- `file is decodable image` → Pillow open() or ffmpeg probe
- `min dimensions` → width ≥ 720, height ≥ 720 (configurable per format)
- `not uniform color` → stddev of pixel values > threshold

#### 3b. Content-level rules
- `no debug text` → OCR-free heuristic: check filename + metadata for known debug patterns:
  - "Escena" / "Seg" / "Placeholder" / "Fallback" / "No image" (in asset metadata or as image text heuristic via filename-based inference)
  - Since we generate placeholders ourselves, we can check `provider=placeholder` or `assetType=placeholder` in metadata

#### 3c. Metadata-level rules
- `provider` is present and not empty
- `query` is present and not empty
- `score` is present and ≥ configurable minimum (default: 30)
- `assetType` is compatible with `editorialRole` (see compatibility matrix)
- `sourceUrl` or attribution is present (for archive assets)

#### 3d. Editorial coherence rules

Compatibility matrix (assetType × editorialRole):

| editorialRole | allowed assetTypes |
|--------------|-------------------|
| context_map | historical_map, map, document, illustration |
| battle_action | historical_photograph, historical_art_or_document, atmospheric_broll, illustration |
| portrait | historical_photograph, historical_art_or_document, painting |
| aftermath | historical_photograph, atmospheric_broll, historical_art_or_document |
| legacy | atmospheric_broll, modern_photograph, historical_photograph |
| abstract | atmospheric_broll, generated_reconstruction, illustration |

Historical coherence per theme uses `period`, `location`, `entities` from visualPlan as metadata filters.

For "La caída de Constantinopla" (medieval/otomano/bizantino):
- negativeKeywords: ["modern", "contemporary", "gun", "tank", "skyscraper", "21st century"]
- requiredPeriodKeywords: ["medieval", "ottoman", "byzantine", "15th century", "1453"]
- forbiddenAssetTypesForRole: { "context_map": ["modern_photograph", "atmospheric_broll"] }

#### 3e. Provider-level rules
- `provider` must be in allowed list for the asset type
- `generated_reconstruction` (AI-generated) is only allowed for `abstract` or `legacy` editorialRoles, or when no archive source is available and score ≥ 50
- Pollinations images are flagged as low-confidence unless manually reviewed

### 4. Quality gate function

```python
def validate_job_for_render(metadata: dict) -> dict:
    """
    Returns:
    {
        "status": "PASS" | "REVIEW_REQUIRED" | "BLOCKED",
        "failures": list[dict],
        "perSegment": list[dict],
        "summary": dict
    }
    """
```

Decision matrix:
| Placeholder found | File invalid | Metadata incomplete | Editorial fail | Score < 30 | Result |
|---|---|---|---|---|---|
| ≥1 | any | any | any | any | BLOCKED |
| 0 | ≥1 | any | any | any | BLOCKED |
| 0 | 0 | ≥2 | ≥1 | any | BLOCKED |
| 0 | 0 | 1 | 0 | any | REVIEW_REQUIRED |
| 0 | 0 | 0 | 0 | ≥1 | REVIEW_REQUIRED |
| 0 | 0 | 0 | 0 | 0 | PASS |

### 5. Integration into render_job.py

```python
def main():
    # ... existing preflight ...
    
    # NEW: Asset validation gate
    if not args.skip_validation:
        asset_result = validate_job_for_render(data)
        if asset_result["status"] == "BLOCKED":
            print("ASSET VALIDATION BLOCKED:")
            for f in asset_result["failures"]:
                print(f"  {f['message']}")
            data["assetValidation"] = asset_result
            data["status"] = "ASSET_FAILED"
            # save metadata
            return 1
        elif asset_result["status"] == "REVIEW_REQUIRED":
            data["assetValidation"] = asset_result
            data["status"] = "REVIEW_REQUIRED"
            # save metadata
            print("WARNING: Asset validation requires review. Rendering anyway.")
        else:
            data["assetValidation"] = asset_result
    
    # ... proceed with render ...
```

### 6. State machine update

```
fetch_images ──► ASSETS_FETCHING ──► ASSETS_READY ──► validate_job_for_render ──┬── PASS ──► RENDER_QUEUED
                                                                                ├── REVIEW_REQUIRED ──► RENDER_QUEUED (with warning)
                                                                                └── BLOCKED ──► ASSET_FAILED (no render)
```

### 7. Test job specification

Before full Constantinopla re-render:

- Duration: 10-15s
- 3 segments
- Scene 1: historical_map of Constantinople from Wikimedia Commons (real asset)
- Scene 2: historical portrait or art (real asset, e.g., Sultan Mehmed II)
- Scene 3: engraving or historical illustration (real asset)
- No Pollinations, no Pexels generic, no CTA
- Audio: synthetic tone or minimal edge-tts
- Subtitles: from cues only, no overlay text
- Must pass validate_job_for_render with status=PASS
