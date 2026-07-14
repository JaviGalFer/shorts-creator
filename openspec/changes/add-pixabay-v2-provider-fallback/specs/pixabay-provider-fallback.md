# Pixabay Provider Fallback — Especificación

## Contracto del provider

### `resolve_pixabay_candidates_v2`

- **Entrada**: lista de queries, api_key, asset_preference, parámetros de búsqueda
- **Salida**: lista de candidatos con provider=pixabay, pageURL como sourceUrl, user como author
- **Errores**: ValueError si api_key vacía o asset_preference no soportada
- **Cache**: 24h TTL, clave determinista sin API key
- **Rate limits**: 100 req/min por defecto, sin retries agresivos

### `download_pixabay_asset_v2`

- **Descarga**: usa `largeImageURL`, guarda en `job_dir/assets/`
- **Validación post-descarga**: Content-Type, tamaño mínimo, dimensiones reales desde cabeceras
- **Rechazo**: elimina archivo y devuelve error si no cumple

## Dimensiones descargadas

- Ancho final >= 720, alto final >= 720 (ambas condiciones)
- Dimensiones esperadas calculadas con relación de aspecto y máximo 1280px
- Dimensiones reales leídas de cabeceras JPEG/PNG/GIF/WebP
- Si no cumplen: archivo eliminado, candidato excluido

## Mapeo assetPreference → Pixabay image_type

| assetPreference | image_type           | Notas                                   |
|-----------------|---------------------|------------------------------------------|
| photograph      | photo               |                                          |
| stock           | photo               |                                          |
| illustration    | illustration, vector| intenta illustration, fallback a vector  |
| diagram         | illustration, vector| soporte débil, con advertencia           |
| archive         | no soportado        | ValueError                               |
| document        | no soportado        | ValueError                               |
| map             | no soportado        | ValueError                               |
| painting        | no soportado        | ValueError                               |
| generated       | no soportado        | ValueError                               |

## Router: cambio en diagram

```python
ROUTING_MATRIX["diagram"] = [
    ("wikimedia_commons", "weak"),
    ("pixabay", "weak"),          # añadido
    ("freeai", "conditional"),
    ("pollinations", "conditional"),
]
```

- Pixabay marcado como `requiresApiKey=True`, `availability=conditional`
- `allowStockAssets=false` excluye Pixabay
- `blockedProviders=["pixabay"]` excluye Pixabay
- Sin API key: Pixabay sigue en candidates pero executor lo salta

## Executor: failover

Orden de intento: según priority en providerCandidates.

Para cada provider candidato:
1. Evaluar disponibilidad (apiKeyPresent, implemented, enabled)
2. Si NO disponible: registrar MISSING_API_KEY/PROVIDER_UNAVAILABLE, continuar
3. Si disponible: ejecutar resolución específica del provider
4. Si RESOLVED: detener
5. Si NO_RESULTS, DOWNLOAD_FAILED, PROVIDER_ERROR: continuar
6. Si INVALID_INPUT: error terminal

Resultado final incluye `providerAttempts` con historial completo.

## Cache Pixabay 24h

- Directorio: `data/cache/pixabay-v2/`
- Clave: SHA-256(query|lang|type|mw|mh|page|per_page)
- No incluye API key
- Escritura atómica
- Cache corrupta → renovar
- No cachear errores 401/403/429

## Credenciales

- `fetch_images_v2.py` lee `PIXABAY_API_KEY` de `os.environ`
- `provider_credentials = {"pixabay": {"apiKey": key}}`
- Pasa a executor, nunca se copia a resultado
- Sin clave: pipeline sigue con Wikimedia

## Contrato de metadata descendente

Candidatos resueltos incluyen:
- provider = "pixabay"
- sourceUrl = pageURL
- fileUrl = largeImageURL
- author = user
- license = "Pixabay Content License"
- tags = tags (si disponible)
- pixabayId = id (si disponible)
