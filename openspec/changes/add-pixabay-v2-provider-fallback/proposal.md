# Propuesta: add-pixabay-v2-provider-fallback

## Problema actual

El pipeline visual v2 depende exclusivamente de Wikimedia Commons como provider de búsqueda. Wikimedia tiene altas tasas de rate-limiting (429), lo que bloquea el E2E completo. El último runtime `e2e-buildd-20260712-001341` resultó en `ASSETS_PARTIAL 4/5` por `PROVIDER_ERROR / RATE_LIMITED` en Wikimedia.

Wikimedia-only se considera insuficientemente fiable para alcanzar `ASSETS_READY` de forma consistente.

## Solución propuesta

Añadir Pixabay como segundo provider de búsqueda con fallback automático:

1. **Cliente Pixabay v2** (`visual_provider_pixabay_v2.py`): stdlib-only, API pública separada en resolución y descarga.
2. **Cache obligatoria de 24h**: reduce tráfico HTTP a Pixabay y cumple sus Términos de Servicio.
3. **Router**: añade Pixabay como fallback débil para `diagram` en la matriz de enrutamiento.
4. **Executor**: failover multiproveedor que recorre `providerCandidates` en orden.
5. **Credenciales**: `PIXABAY_API_KEY` gestionada mediante `provider_credentials`, nunca expuesta.

## Alcance

- Provider Pixabay: búsqueda + descarga + cache 24h + validación de dimensiones
- Mapeo `assetPreference → image_type` (photograph/stock→photo, illustration/diagram→illustration/vector)
- Router: Pixabay como P2 en `diagram` con soporte débil
- Executor: failover real entre Wikimedia y Pixabay
- `fetch_images_v2.py`: lectura de `PIXABAY_API_KEY` del entorno

## Fuera de alcance

- Pexels, FreeAI, Pollinations
- Modificación del cliente Wikimedia
- Voz, audio, subtítulos, FFmpeg
- Auditoría general del código
- Modos de dominio

## Criterios de éxito

1. Tests pasando sin regresiones (baseline: 1008 passed, 16 failed preexistentes)
2. Pixabay provider con 57 tests unitarios (sin HTTP real)
3. Executor con 10 tests de failover multiproveedor
4. Router con 9 tests de diagram+pixabay
5. Sin secretos en outputs, logs, cache ni metadata
6. E2E con 5/5 assets usando Wikimedia primario + Pixabay fallback (si hay API key)

## Riesgos

- Bajo: Pixabay es read-only, sin dependencias nuevas, stdlib-only
- Cache de 24h obligatorio por ToS de Pixabay
- Pixabay no garantiza diagramas técnicos precisos (advertencia documentada)
