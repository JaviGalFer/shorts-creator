# Diseño: visual-fidelity-runtime

## Arquitectura elegida

**Dependencia Python opcional dentro del proceso** (la alternativa de servicio/proceso separado queda descartada; ver al final).

```
src/shorts_creator/assets/visual_fidelity.py   (NUEVO)
  ├─ score_visual_fidelity(image_path, text) -> dict | None
  ├─ backend OpenCLIP cargado lazy + cacheado una vez por proceso
  ├─ dispositivo: CUDA si torch.cuda.is_available() else CPU
  ├─ GIF: frame 0, convert RGB (no muta el archivo)
  └─ fallo de carga -> status UNAVAILABLE -> bypass explícito

src/shorts_creator/assets/executor.py   (MODIFICADO)
  └─ gate post-descarga / pre-RESOLVED en _resolve_wikimedia y _resolve_pixabay
       metadata gate (existente) -> download -> pixel gate -> RESOLVED / reject

src/shorts_creator/assets/bridge.py     (MODIFICADO)
  └─ propaga visualFidelityAssessment al metadata assets segment

tests/test_visual_fidelity_runtime.py   (NUEVO)
  └─ unit tests SIN pesos: mocks del backend, sin importar torch/open_clip real
```

## Contrato del componente (visual_fidelity.py)

`score_visual_fidelity(image_path: Path, text: str) -> dict | None`:

- `{"status": "SCORED", "score": float, "method": "openclip_vit_b32_p1",
   "architecture": "ViT-B-32", "pretrained": "laion2b_s34b_b79k",
   "device": "cuda"|"cpu", "gifFrame": 0|None}`
- `{"status": "UNAVAILABLE", "reason": "..."}` → el executor hace bypass con warning de telemetría.
- `None` equivalente a `UNAVAILABLE` (gate desactivado por falta de configuración → `DISABLED`).

Contrato de configuración:
- Threshold explícito vía env/config (`VISUAL_FIDELITY_THRESHOLD`). Sin threshold → gate `DISABLED` (bypass) con warning. **`0.2296` nunca se codifica como default.**
- Activation también controlada por flag si se desea mantener el gate off en producción hasta validar.

### Modelo y scoring

- OpenCLIP `ViT-B-32`, pretrained `laion2b_s34b_b79k`, tokenizer del mismo arch, `model.eval()`.
- Text policy P1: `queryUsed` raw (sin templates).
- Score: similitud coseno normalizada `encode_image · encode_text`, batch=1, `torch.no_grad()` — idéntico al benchmark Slice 2 (reproducibilidad GPU==CPU <1e-6 ya medida).
- El backend se importa **lazy** (imports de `torch`/`open_clip` dentro de la función o del inicializador), de modo que el runtime base nunca importa dependencias opcionales.

### Lifecycle

- Carga en el primer uso (lazy); singleton por proceso con lock simple en la primera inicialización (thread-safe).
- La carga ocurre UNA vez y se reutiliza para todos los candidatos del job y jobs posteriores en el mismo proceso.
- Descarga de pesos a caché local del usuario/HF (fuera del repo). El repo nunca contiene pesos.

## Integración en executor

Punto exacto: tras `download_*_asset_v2` OK y ANTES de construir el dict `RESOLVED`, tanto en `_resolve_wikimedia` como en `_resolve_pixabay`:

```
dl_result = download_*(...)
if dl_result["ok"]:
    vf = score_visual_fidelity(absolute_path, query_used)
    if gate disabled or unavailable:          # bypass explícito
        warning + telemetría VISUAL_FIDELITY_DISABLED / _UNAVAILABLE
        -> continuar con RESOLVED (gate abierto, telemetría persistida)
    elif vf.score >= threshold:
        -> RESOLVED con visualFidelityAssessment persistido
    else:
        -> REJECT: borrar archivo descargado, registrar visualFidelityRejections,
           añadir URLs a excluded sets, CONTINUAR con siguiente candidato
```

- Se agotan los candidatos con rechazos de fidelidad → `NO_RESULTS` con `visualFidelityRejections` (mismo patrón que `semanticRejections`).
- El gate solo aplica a estrategias `search` post-descarga (providers con archivo); no aplica a estrategias `generation`.
- Provider-agnostic: únicamente `queryUsed` + archivo de imagen.

## Telemetría persistida

En el asset resuelto (`visualFidelityAssessment`):

```json
{
  "status": "SCORED" | "UNAVAILABLE" | "DISABLED",
  "method": "openclip_vit_b32_p1",
  "architecture": "ViT-B-32",
  "pretrained": "laion2b_s34b_b79k",
  "textPolicy": "p1",
  "textUsed": "<queryUsed>",
  "score": 0.31,
  "threshold": 0.25,
  "verdict": "ACCEPT" | "REJECT" | "BYPASS",
  "device": "cuda" | "cpu",
  "gifFrame": 0 | null
}
```

Y en `unresolvedSegments` (`visualFidelityRejections`) para cada candidato rechazado por el pixel gate. `bridge.py` propaga `visualFidelityAssessment` al shape de metadata `assets[].segments[]`.

## Dependencias y model lifecycle

- NO añadir `torch` / `open_clip_torch` a `requirements.txt` base.
- Extra opcional documentado (sección comentada en requirements.txt o runbook) con comando de instalación y caché de pesos fuera del repo.
- El modelo se carga una vez por proceso (lazy) y se reutiliza.
- La decisión de memoria (RSS ~1.5 GiB CPU medido; 690 MiB max allocated GPU) es operativa y documentada, no un límite hardcodeado.

## GIF frame 0

`visual_fidelity.py` siempre evalúa el frame 0 de GIFs (consistente con el benchmark humano y Slice 2). Se registra `gifFrame: 0` en telemetría. El archivo original no se muta.

## Tests sin pesos ni descargas

`tests/test_visual_fidelity_runtime.py`:

- Mocks del backend (fakes de `encode_image`/`encode_text`/tokenizer); sin importar torch/open_clip reales.
- Singleton/lazy-load: la carga ocurre una sola vez.
- Fallo de import/load → `UNAVAILABLE` → bypass.
- Dispositivo: CPU forzado; CUDA con `torch.cuda.is_available` mockeado.
- Umbral: score >= threshold → ACCEPT; < threshold → REJECT; sin threshold → DISABLED.
- GIF frame 0 con imagen sintética animada (PIL), original no mutado.
- Integración executor con mocks: rechazo borra archivo y pasa al siguiente candidato; ausencia de OpenCLIP → bypass con warning/telemetría.
- Bridge: propaga `visualFidelityAssessment`.
- Sin red, sin descarga de pesos, sin imports de torch/open_clip a nivel de módulo en runtime (lazy-import).

## Alternativas descartadas

1. **Servicio/proceso local separado** (IPC socket/HTTP): descartado para el MVP.
   - + aislamiento de memoria/crashes, reutilización entre jobs.
   - - IPC + serialización de imágenes, gestión de lifecycle del servicio, estado en frío (carga por primera request), más superficie operativa (supervisión, reinicios). Complejidad sin justificar para un pipeline batch por job.
   - Se reconsidera si el RSS ~1.5 GiB resultara problemático en el despliegue.

## Fases de implementación

- **Slice 1 (COMPLETADO)**: `visual_fidelity.py` (componente, lazy singleton, CPU/CUDA, GIF frame 0, threshold configurable sin default 0.2296) + `tests/test_visual_fidelity_runtime.py` (unit con mocks). Sin integración.
- **Slice 2 (COMPLETADO)**: integración en `executor.py` (gate post-descarga wikimedia/pixabay, rechazo → siguiente candidato, bypass UNAVAILABLE/DISABLED), `bridge.py` (telemetría), tests de flujo + suite completa.
- **Slice 3 (COMPLETADO)**: validación/calibración real contra corpus canónico con el componente runtime real, fijación de threshold validado (siempre candidato/versionado, NUNCA default), activación controlada (env), docs operativas.

## Slice 3 (COMPLETADO) — evidencia runtime real

Validación con el componente runtime real `score_visual_fidelity` (NO el benchmark antiguo) sobre el corpus canónico de 38 assets. Entorno: venv externo `/tmp/shorts-visual-fidelity-gpu-venv` (torch 2.11.0+cu128, open_clip_torch 3.3.0, Pillow 12.3.0), caché HF `/tmp/shorts-visual-fidelity-hf`, dispositivo **cuda** (NVIDIA GeForce GTX 1650 SUPER, 4 GB). Pocos weights descargados (caché reutilizada de Slice 2). Threshold provisional de validación: `VISUAL_FIDELITY_THRESHOLD=0.2296`.

- 38/38 `SCORED`, 0 `UNAVAILABLE`/`DISABLED` (gate operativo, sin bypass).
- **25/30 retained + 7/8 badRejected** — reproduce EXACTAMENTE el benchmark Slice 2.
- `goodAssetRetention=0.8333`, `badAssetRejectionRecall=0.875`, `falseAcceptances=1`, `falseRejections=5`.
- Verdicts idénticos al benchmark; **scores coinciden al <1e-6** (max abs diff 6.1e-07, mean 1.5e-07) — reproducibilidad GPU/CPU del runtime confirmada sobre los mismos 38 assets.
- Único bad no rechazado: ilustración moderna del Porsche (`la-2026-08-17-234123/scene_002_seg_002.png`) — fidelidad entidad/temporal, caso conocido y aceptado.
- Good assets falsamente rechazados (5): aurora night-sky PNG, diagrama Earth-solar, volcán paisaje, VR headset, gráfico amortización — mismos 5 del benchmark previo.
- Latencia medida (incluye carga del modelo al inicio): total 5.4 s (load ~4.3 s + scoring); mediana 24.5 ms, p95 214 ms, máx 3.8 s (primera llamada: warmup/Kernel CUDA). Rows crudas en `data/evaluations/visual-fidelity-runtime/runtime-validation.json` (git-ignored).
- Target alcanzado: retained >= 24/30 ✓ y badRejected >= 6/8 ✓.

## Activación y operación (decidido en Slice 3)

- **Gate OFF por defecto.** Sin `VISUAL_FIDELITY_THRESHOLD` el gate devuelve `DISABLED` y el pipeline se comporta exactamente como antes (bypass + assessment persistido).
- **`VISUAL_FIDELITY_THRESHOLD` es la única superficie de activación** (explícita, por proceso/job). `0.2296` queda registrado como **threshold validado/candidato versionado en la documentación del change** — NUNCA como default hardcodeado en `visual_fidelity.py`.
- Para activarlo en un job: `VISUAL_FIDELITY_THRESHOLD=0.2296 python3 bin/run_job.py ...`. Sin la variable, el modelo NO se carga (ahorro de ~1.5 GiB RSS / VRAM y tiempo de arranque).
- No se añade `torch`/`open_clip` a `requirements.txt` base; el stack es una dependencia opcional instalada en el entorno de ejecución (idealmente con CUDA si hay GPU).
- Instalación opcional (no es dep del proyecto): `pip install open_clip_torch` (+ `torch`/`torchvision` con CUDA si se desea GPU). Los pesos de `ViT-B-32/laion2b_s34b_b79k` se cachean en el HF hub del usuario (p.ej. `$HF_HOME/hub/models--laion--CLIP-ViT-B-32-laion2B-s34B-b79K`); el repo nunca contiene pesos.
- Memoria: CPU ~1.5 GiB RSS (medido en benchmark Slice 2); GPU máximo 690.6 MiB asignados (GTX 1650 SUPER 4 GB).