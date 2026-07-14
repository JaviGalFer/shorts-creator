# Diseño: add-pixabay-v2-provider-fallback

## Arquitectura

```
fetch_images_v2.py
  ├─ visual_provider_config_v2  (provider_config + pixabayApiKeyPresent)
  ├─ visual_plan_v2             (canonicalize)
  ├─ visual_asset_router_v2     (build sourcing plan with diagram+pixabay)
  ├─ visual_asset_executor_v2   (multi-provider failover)
  │   ├─ visual_provider_wikimedia_v2  (primary)
  │   └─ visual_provider_pixabay_v2    (fallback) [NUEVO]
  └─ visual_asset_bridge_v2     (map to metadata)
```

## Provider Pixabay v2

### API pública

```python
def resolve_pixabay_candidates_v2(
    queries, *, api_key, asset_preference,
    min_width, min_height, language, max_results,
    cache_dir, cache_ttl_sec,
    excluded_source_urls, excluded_file_urls, timeout,
) -> list[dict]

def download_pixabay_asset_v2(
    candidate, output_path, *, timeout, min_size_bytes,
) -> dict
```

### Mapeo assetPreference → image_type

| assetPreference | image_type           |
|-----------------|---------------------|
| photograph      | photo               |
| stock           | photo               |
| illustration    | illustration, vector|
| diagram         | illustration, vector|

No soportado: archive, document, map, painting, generated.

### Dimensiones

Pixabay devuelve `imageWidth`/`imageHeight` del original. `largeImageURL` escala a máximo ~1280px.

Se calculan dimensiones esperadas conservando relación de aspecto con máximo 1280. Validación pre-descarga con `is_v2_asset_dimension_renderable`.

Post-descarga: lectura real de dimensiones desde cabeceras del archivo (JPEG/PNG/GIF/WebP) sin dependencias externas.

### Cache 24h

- Ubicación: `data/cache/pixabay-v2/`
- Clave: SHA-256 de query, language, image_type, min_width, min_height, page, per_page
- TTL: 86400s
- Escritura atómica (`.tmp` + `os.replace`)
- No incluye API key en nombre, contenido ni metadata

## Router

Cambio mínimo en `ROUTING_MATRIX`:

```python
"diagram": [
    ("wikimedia_commons", "weak"),
    ("pixabay", "weak"),          # NUEVO
    ("freeai", "conditional"),
    ("pollinations", "conditional"),
],
```

Con advertencia en `MATRIX_WARNINGS`:

```text
Pixabay illustration/vector fallback may not represent a precise technical diagram
```

## Executor: failover multiproveedor

Política de failover en live mode:

| Status anterior    | Acción                        |
|--------------------|-------------------------------|
| RESOLVED           | Detener, devolver asset       |
| PROVIDER_UNAVAILABLE / MISSING_API_KEY | Continuar siguiente |
| NO_RESULTS         | Continuar siguiente           |
| DOWNLOAD_FAILED    | Continuar siguiente           |
| PROVIDER_ERROR / RATE_LIMITED | Continuar siguiente |
| INVALID_INPUT      | Error terminal del segmento   |

Si ningún provider resuelve: devolver status más informativo con `providerAttempts`.

### providerAttempts

```json
{
  "providerAttempts": [
    {"provider": "wikimedia_commons", "status": "PROVIDER_ERROR", "reason": "RATE_LIMITED"},
    {"provider": "pixabay", "status": "RESOLVED", "reason": null}
  ]
}
```

## Credenciales

Flujo:

1. `fetch_images_v2.py` lee `PIXABAY_API_KEY` de `os.environ`
2. Construye `provider_credentials = {"pixabay": {"apiKey": "..."}}`
3. Pasa a `execute_visual_sourcing_plan_v2(..., provider_credentials=...)`
4. Executor pasa credenciales a `_resolve_pixabay` sin copiarlas al resultado

Sin clave: `availability = MISSING_API_KEY`, pipeline sigue con Wikimedia únicamente.

## Gestión de secretos

- `provider_credentials` nunca se copia al resultado
- Nunca se imprime, persiste ni mezcla con provider_config
- `SECRET_FIELD_NAMES` en executor bloquea campos tipo apiKey en provider_config
- Cache de Pixabay no contiene API key
- `.env.example` ya incluye `PIXABAY_API_KEY=` (existente)
