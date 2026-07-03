# Spec: Modern Asset Blocking Outside Legacy Context

## Regla de negocio

Un asset visual moderno (Pexels, b-roll contemporáneo, fotos de calles/edificios actuales) SOLO puede aparecer si:

1. **`editorialRole == "consequence_or_legacy"`** (o cualquier otro soft role de legado), Y
2. El **texto del voiceover** en ese narrative beat menciona explícitamente el presente, legado o consecuencia contemporánea.

## Detección de asset moderno

```python
MODERN_INDICATORS = {
    "providers": {"pexels", "pixabay"},
    "asset_types": {"atmospheric_broll", "modern_photograph", "broll"},
    "query_keywords": {
        "street", "car", "cars", "building", "modern", "today",
        "people walking", "city street", "istanbul today", "modern istanbul",
        "contemporary", "present day", "current"
    }
}

def is_modern_asset(segment: dict) -> bool:
    provider = (segment.get("provider") or "").lower()
    if provider in MODERN_INDICATORS["providers"]:
        return True
    at = (segment.get("assetType") or "").lower()
    if at in MODERN_INDICATORS["asset_types"]:
        return True
    # También verificar la query usada
    return False
```

## Keywords de legado presente

```python
LEGACY_KEYWORDS = {
    "hoy", "hoy en día", "actual", "actualmente", "hoy día",
    "Estambul", "moderno", "moderna", "legado", "consecuencia",
    "contemporáneo", "contemporánea", "presente", "hoy,",
    "en la actualidad", "a día de hoy", "todavía", "aún",
    "today", "present", "modern", "legacy", "istanbul"
}
```

## Validación

```python
def check_modern_asset_context(segment: dict, beat_text: str, editorial_role: str) -> list:
    if not is_modern_asset(segment):
        return []

    if editorial_role not in SOFT_ROLES:
        return [{
            "rule": "modern_asset_hard_role",
            "message": f"Modern asset in hard historical role '{editorial_role}'"
        }]

    text_lower = beat_text.lower()
    has_legacy_keyword = any(kw in text_lower for kw in LEGACY_KEYWORDS)

    if not has_legacy_keyword:
        return [{
            "rule": "modern_asset_no_legacy_context",
            "message": f"Modern asset without legacy/contemporary keywords in narration"
        }]

    return []
```

## Resultado

- `modern_asset_hard_role` → BLOCKED (no negociable)
- `modern_asset_no_legacy_context` → BLOCKED (el texto debe justificar el asset moderno)
- Si pasa ambas → permitido

## Integración en asset_validation.py

Añadir después de `check_provider_allowed()`:

```python
for seg_entry, seg in zip(seg_entries, segments):
    beat_text = ""  # obtener del narrativeBeat correspondiente
    editorial_role = seg_entry.get("editorialRole", "")
    failures = check_modern_asset_context(seg, beat_text, editorial_role)
    seg_failures.extend(failures)
```
