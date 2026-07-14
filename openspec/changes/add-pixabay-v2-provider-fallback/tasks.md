# Tasks: add-pixabay-v2-provider-fallback

- [x] Crear cliente `visual_provider_pixabay_v2.py` stdlib-only
- [x] Implementar `resolve_pixabay_candidates_v2` con búsqueda + cache 24h
- [x] Implementar `download_pixabay_asset_v2` con validación MIME y dimensiones
- [x] Mapeo `assetPreference → image_type`
- [x] Validación dimensiones post-descarga (stdlib, cabeceras JPEG/PNG/GIF/WebP)
- [x] Cache obligatoria 24h en `data/cache/pixabay-v2/`
- [x] Gestión API key mediante `provider_credentials`
- [x] Router: añadir Pixabay como fallback débil para `diagram`
- [x] Executor: failover multiproveedor con `providerAttempts`
- [x] `fetch_images_v2.py`: leer `PIXABAY_API_KEY` de entorno
- [x] `load_provider_config_v2`: parámetros `pixabay_live`, `pixabay_api_key_present`
- [x] `.env.example`: ya incluye `PIXABAY_API_KEY=`
- [x] Tests Pixabay provider: 57 tests
- [x] Tests executor multi-provider: 10 tests
- [x] Tests router diagram+pixabay: 9 tests
- [x] E2E live: 5/5 ASSETS_READY, prepare/render/validate completados
- [x] 1084 passed, 16 pre-existing failures, sin regresiones
