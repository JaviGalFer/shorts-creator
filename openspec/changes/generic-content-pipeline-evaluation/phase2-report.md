# Informe Fase 2: generic-content-pipeline-evaluation

**Estado:** COMPLETADO / VERIFICADO / CLOSED tras la revisión visual externa multimodal de los 38 assets resueltos (contact sheets en `data/evaluations/genericity-phase2-visual-review/`).

**Sobre la revisión visual:** la revisión de píxeles se completó EXTERNAMENTE desde los cuatro contact sheets generados (modelo multimodal). Las clasificaciones visuales de este informe ya NO son provisionales: reflejan inspección de píxeles.

**Totales de revisión visual (38 resueltos):**
- `CLEARLY_RELEVANT`: 16
- `COARSE_BUT_USABLE`: 14
- `FALSE_POSITIVE_OR_UNUSABLE`: 8

---

## 0. Tabla de los 8 jobs (evidencia de runtime, radicada)

Ejecutados secuencialmente con configuración de runtime NO modificada entre jobs, comando canónico:

```
python bin/run_job.py --topic "<TOPIC>" --duration-preset quick_30 \
  --asset-providers wikimedia_commons,pixabay --stop-after assets
```

| # | Tema | jobId | status | attempts/retries | scenes | durBootstrap | res/unres |
|---|------|-------|--------|------------------|--------|--------------|-----------|
| 1 | Cómo se forma una aurora boreal | `cmo-2026-08-17-233901` | ASSETS_PARTIAL | retries=0 (attempt 1) | 5 | PASS | 6/1 |
| 2 | La evolución del Porsche 911 | `la-2026-08-17-234123` | ASSETS_PARTIAL | retries=0 | 5 | **FAIL** (telemetría) | 8/2 |
| 3 | Cómo funciona Spring Boot | `cmo-2026-08-17-234325` | ASSETS_PARTIAL | retries=0 | 5 | **FAIL** (telemetría) | 3/7 |
| 4 | Por qué cayó el Imperio Romano | `por-2026-08-17-234531` | ASSETS_PARTIAL | retries=0 | 5 | PASS | 4/5 |
| 5 | Cómo cazan los pulpos | `cmo-2026-08-17-234735` | ASSETS_PARTIAL | retries=0 | 5 | PASS | 5/4 |
| 6 | Qué ocurre dentro de un volcán | `qu-2026-08-17-234954` | ASSETS_PARTIAL | retries=0 | 5 | PASS | 6/3 |
| 7 | Cómo evolucionaron los videojuegos 3D | `cmo-2026-08-17-235250` | ASSETS_PARTIAL | retries=0 | 5 | PASS | 2/8 |
| 8 | Cómo funciona una hipoteca | `cmo-2026-08-17-235456` | ASSETS_PARTIAL | retries=0 | 5 | **FAIL** (telemetría) | 4/2 |

Notas:
- Ningún job entró en `REVIEW_REQUIRED`; todos los scripts pasaron en attempt 1 (retries 0). Sin fallo de infraestructura/auth/API.
- Los 3 `durBootstrap=FAIL` (Porsche, Spring Boot, hipoteca) SON telemetría no bloqueante: el script fue estructuralmente VÁLIDO y siguió igualmente. Confirma el contrato A.
- Total queries persistidas evaluadas con el guard de especificidad: **0 VAGUE** en los 8 temas (16–20 queries por job, todas `VALID`).

---

## 1. Evaluación por tema — SCRIPT y VISUAL PLAN

### 1) Aurora boreal — `cmo-2026-08-17-233901`
- **Script:** coherente, aborda el tema (partículas solares → atmósfera → colores). Sin alucinación factual. Progresión correcta. Error gramatical menor "El próximo vez" (no factual).
- **VisualPlan:** subjects y queries concretos (aurora borealis, solar particles, atmosphere); las queries siguen la intención narrativa por escena. `assetPreferences` apropiadas (photograph/diagram).
- **Query/intent:** bien alineado.

### 2) Porsche 911 — `la-2026-08-17-234123`
- **Script:** coherente y correcto (lanzamiento 1964). Sin alucinación.
- **VisualPlan:** concreto (Porsche 911 clásico → evolución → tecnología → legado). Algunas queries de segmento genéricas ("sports cars history diagram"). Apropiado.
- **Query/intent:** bien alineado en su mayoría.

### 3) Spring Boot — `cmo-2026-08-17-234325`
- **Script:** coherente, aborda el tema (auto-configuración, inicio rápido, integraciones). Sin alucinación factual grave. superficial pero correcto para 30s.
- **VisualPlan:** queries de sustantivos concretos ("Spring Boot logo", "Java code snippet", "project structure diagram"). Las queries son razonables y recuperables; el tema abstracto traduce a sustantivos buscables.
- **Query/intent:** correcto (no es un fallo de generación de query).

### 4) Imperio Romano — `por-2026-08-17-234531`
- **Script:** coherente, aborda el tema (luchas internas, corrupción, invasiones germánicas, 476 d.C.). El sujeto "caóres" (escena 2) es un token garbled/no-palabra; "Colonia de Rávena" es impreciso (Rávena era ciudad, no colonia). Sin error factual mayor.
- **VisualPlan:** queries concretas ("map of Roman Empire", "Germanic tribes invasion", "fall of Roman Empire"). Apropiadas.
- **Query/intent:** correcto.

### 5) Pulpos — `cmo-2026-08-17-234735`
- **Script:** coherente, aborda el tema (camuflaje, tentáculos, veneno). Sin alucinación.
- **VisualPlan:** querente concreto (octopus camouflage, tentacles, venom). Apropiado.
- **Query/intent:** correcto.

### 6) Volcán — `qu-2026-08-17-234954`
- **Script:** coherente, aborda el tema (magma, corteza, presión, erupción). Sin alucinación.
- **VisualPlan:** concreto (volcano eruption, magma, ash, lava). Apropiado.
- **Query/intent:** correcto.

### 7) Videojuegos 3D — `cmo-2026-08-17-235250`
- **Script:** coherente. Matiz factual menor: "En 1995, 'Doom' revolucionó" — Doom salió en 1993 (Doom II 1994); 1995 como año revolucionario es impreciso pero no desvirtúa el tema.
- **VisualPlan:** querente concreto ("Doom 1995 video game screenshot", "PlayStation Nintendo 64 comparison"). Apropiado.
- **Query/intent:** correcto.

### 8) Hipoteca — `cmo-2026-08-17-235456`
- **Script:** coherente y correcto (préstamo, intereses, amortización). Sin alucinación.
- **VisualPlan:** querente concreto (house mortgage signing, interest calculator, amortization chart). Nota: la query del segmento 1 de escena 4 es "amortization chart graph photograph" pero `assetPreference=diagram` (leve desajuste query/preferencia, no bloqueante).
- **Query/intent:** correcto.

**Conclusión SCRIPT/PLAN:** en los 8 temas sin relación, el LLM produjo script + VisualPlan estructuralmente válidos, con queries concretas y `VALID`, sin ramas de dominio ni alucinaciones mayores → **la capa script/VisualPlan se comporta de forma genérica y de calidad uniforme.**

---

## 2. Matriz ASSETS resuelto / no resuelto

| # | Tema | totalSeg | res | unres | ratio | prov resuelto |
|---|------|----------|-----|-------|-------|---------------|
| 1 | Aurora | 7 | 6 | 1 | 0.86 | wikimedia_commons, pixabay |
| 2 | Porsche | 10 | 8 | 2 | 0.80 | wikimedia_commons, pixabay |
| 3 | Spring Boot | 10 | 3 | 7 | 0.30 | pixabay |
| 4 | Roma | 9 | 4 | 5 | 0.44 | pixabay |
| 5 | Pulpos | 9 | 5 | 4 | 0.56 | pixabay |
| 6 | Volcán | 9 | 6 | 3 | 0.67 | pixabay |
| 7 | Videojuegos | 10 | 2 | 8 | 0.20 | pixabay |
| 8 | Hipoteca | 6 | 4 | 2 | 0.67 | pixabay |

Todas las `semanticAssessment.verdict == RELEVANT` (gate pasó todo lo resuelto). No hay `UNRESOLVED` por router (`UNROUTABLE`); los no resueltos son `NO_RESULTS` o `DOWNLOAD_FAILED` (ver §4).

---

## 3. Detalle de assets resueltos (queryUsed · provider · fuente) — METADATA_ONLY (contexto de identificación)

Esta tabla es el registro de identificación por metadata (NO inspección visual). La clasificación VISUAL final por asset está en §3.1.

### 1) Aurora — `data/videos/cmo-2026-08-17-233901/assets/`
| seg | queryUsed | prov | path | METADATA_ONLY_ASSESSMENT |
|-----|-----------|------|------|--------------------------|
| s1.1 | aurora borealis night sky photograph | wikimedia | scene_001_seg_001.png | on-topic |
| s1.2 | aurora borealis solar particles photograph | wikimedia | scene_001_seg_002.jpg | on-topic |
| s2.1 | solar flares photograph | wikimedia | scene_002_seg_001.jpg | on-topic |
| s3.1 | Earth atmosphere solar particles interaction diagram | pixabay | scene_003_seg_001.png | probable diagrama on-topic |
| s4.1 | aurora borealis colors photograph | pixabay | scene_004_seg_001.jpg | on-topic |
| s5.1 | aurora borealis night sky photograph | wikimedia | scene_005_seg_001.gif | on-topic |

### 2) Porsche — `data/videos/la-2026-08-17-234123/assets/`
| seg | queryUsed | prov | path | METADATA_ONLY_ASSESSMENT |
|-----|-----------|------|------|--------------------------|
| s1.1 | Porsche 911 classic car photograph | wikimedia | scene_001_seg_001.jpg | on-topic |
| s1.2 | Porsche 911 classic car photograph | wikimedia | scene_001_seg_002.jpg | on-topic |
| s2.1 | Porsche 911 1964 photograph | pixabay | scene_002_seg_001.jpg | on-topic |
| s2.2 | Porsche 911 original model illustration | pixabay | scene_002_seg_002.png | **COARSE** (GT3 RS moderno, no el 911 de 1964) |
| s3.1 | Porsche 911 evolution comparison photograph | pixabay | scene_003_seg_001.jpg | on-topic |
| s4.1 | Porsche 911 advanced technology photograph | pixabay | scene_004_seg_001.jpg | on-topic |
| s5.1 | Porsche 911 legacy photograph | pixabay | scene_005_seg_001.jpg | on-topic |
| s5.2 | sports cars history diagram | pixabay | scene_005_seg_002.png | **PROBABLE FALSE POSITIVE** (vector `courts-tennis-two-green-grass`, pista de tenis, no coches) |

### 3) Spring Boot — `data/videos/cmo-2026-08-17-234325/assets/`
| seg | queryUsed | prov | path | METADATA_ONLY_ASSESSMENT |
|-----|-----------|------|------|--------------------------|
| s1.2 | developer programming code editor photograph | pixabay | scene_001_seg_002.jpg | coarse (código genérico) |
| s2.2 | Java code snippet photograph | pixabay | scene_002_seg_002.jpg | coarse (código genérico) |
| s3.1 | Spring Boot project structure diagram | pixabay | scene_003_seg_001.png | **PROBABLE FALSE POSITIVE** (ilustración `workflow-planning-process`, no estructura de proyecto Spring) |

### 4) Roma — `data/videos/por-2026-08-17-234531/assets/`
| seg | queryUsed | prov | path | METADATA_ONLY_ASSESSMENT |
|-----|-----------|------|------|--------------------------|
| s1.2 | Roman Empire historical scenes | pixabay | scene_001_seg_002.jpg | on-topic (Foro Romano) |
| s2.2 | Roman Empire conflicts illustration | pixabay | scene_002_seg_002.png | coarse (pintura de Julio César) |
| s3.1 | Germanic tribes invasion photograph | pixabay | scene_003_seg_001.jpg | **PROBABLE FALSE POSITIVE** (`fishermans-hut-old-abandoned`, no tribus germánicas) |
| s4.2 | fall of Roman Empire illustration | pixabay | scene_004_seg_002.png | **PROBABLE FALSE POSITIVE** (`ai-generated-roman-woman-portrait`, retrato, no caída del imperio) |

lote: NOTE — 2 de 4 resueltos probablemente off-topic.

### 5) Pulpos — `data/videos/cmo-2026-08-17-234735/assets/`
| seg | queryUsed | prov | path | METADATA_ONLY_ASSESSMENT |
|-----|-----------|------|------|--------------------------|
| s2.1 | octopus camouflage reef photograph | pixabay | scene_002_seg_001.jpg | on-topic |
| s2.2 | octopus hiding in coral photograph | pixabay | scene_002_seg_002.jpg | on-topic |
| s3.1 | octopus tentacles catching prey photograph | pixabay | scene_003_seg_001.jpg | on-topic |
| s4.1 | blue ringed octopus venom photograph | pixabay | scene_004_seg_001.jpg | on-topic |
| s5.1 | octopus underwater environment photograph | pixabay | scene_005_seg_001.jpg | on-topic |

### 6) Volcán — `data/videos/qu-2026-08-17-234954/assets/`
| seg | queryUsed | prov | path | METADATA_ONLY_ASSESSMENT |
|-----|-----------|------|------|--------------------------|
| s1.1 | volcano eruption lava flow photograph | pixabay | scene_001_seg_001.jpg | on-topic |
| s2.2 | earth crust diagram | pixabay | scene_002_seg_002.png | on-topic (diagrama geología) |
| s3.2 | volcano explosion photograph | pixabay | scene_003_seg_002.jpg | on-topic |
| s4.1 | volcanic ash eruption photograph | pixabay | scene_004_seg_001.jpg | on-topic |
| s4.2 | lava flow photograph | pixabay | scene_004_seg_002.jpg | on-topic |
| s5.1 | volcano landscape photograph | pixabay | scene_005_seg_001.jpg | on-topic |

### 7) Videojuegos 3D — `data/videos/cmo-2026-08-17-235250/assets/`
| seg | queryUsed | prov | path | METADATA_ONLY_ASSESSMENT |
|-----|-----------|------|------|--------------------------|
| s3.1 | PlayStation Nintendo 64 comparison photograph | pixabay | scene_003_seg_001.jpg | **COARSE** (joystick/controlador genérico, no comparación consolas) |
| s4.1 | modern 3D video games immersive experience photograph | pixabay | scene_004_seg_001.jpg | coarse (VR headset, temáticamente inmersión) |

### 8) Hipoteca — `data/videos/cmo-2026-08-17-235456/assets/`
| seg | queryUsed | prov | path | METADATA_ONLY_ASSESSMENT |
|-----|-----------|------|------|--------------------------|
| s1.1 | house mortgage signing contract photograph | pixabay | scene_001_seg_001.jpg | on-topic |
| s2.1 | person mortgage office agent photograph | pixabay | scene_002_seg_001.jpg | coarse |
| s3.1 | mortgage interest calculator photograph | pixabay | scene_003_seg_001.jpg | on-topic |
| s4.1 | amortization chart graph photograph | pixabay | scene_004_seg_001.png | **PROBABLE FALSE POSITIVE** (gráfico `interface-internet-program-browser`, no tabla de amortización) |

### 3.1 Revisión visual final por asset (inspección de píxeles, revisión externa)

Clasificación visual por asset (contact sheets): `CR`=CLEARLY_RELEVANT, `CU`=COARSE_BUT_USABLE, `FP`=FALSE_POSITIVE_OR_UNUSABLE.

**1) Aurora — 6 resueltos (CR 2, CU 2, FP 2) → USABLE_WITH_LIMITATIONS**
- s1.1 aurora night sky (wm) — CR
- s1.2 aurora solar particles (wm) — **FP**: instalación nocturna/antena, no partículas sobre aurora
- s2.1 solar flares (wm) — CR
- s3.1 Earth-solar diagram (px) — CU
- s4.1 aurora colors (px) — CU
- s5.1 aurora night-sky GIF (wm) — **FP**: primer frame prácticamente en blanco/inutilizable

**2) Porsche 911 — 8 resueltos (CR 3, CU 3, FP 2) → USABLE_WITH_LIMITATIONS**
- s1.1 classic car (wm) — CR
- s1.2 classic car (wm) — CR
- s2.1 Porsche 911 1964 (px) — CU
- s2.2 original model illustration (px) — **FP**: ilustración de modelo de rendimiento moderno, no el 911 original
- s3.1 evolution comparison (px) — CU
- s4.1 advanced technology (px) — CU
- s5.1 legacy (px) — CR
- s5.2 sports cars history diagram (px) — **FP**: diagrama de pista de tenis

**3) Spring Boot — 3 resueltos (CR 1, CU 1, FP 1) → USABLE_WITH_LIMITATIONS**
- s1.2 developer code editor (px) — CU
- s2.2 Java code snippet (px) — CR
- s3.1 project structure diagram (px) — **FP**: ilustración genérica web/workflow

**4) Imperio Romano — 4 resueltos (CR 1, CU 1, FP 2) → SYSTEMIC_FAILURE (capa de assets)**
- s1.2 Roman Empire historical scenes (px) — CR (Foro Romano)
- s2.2 Roman Empire conflicts illustration (px) — CU (pintura de Julio César)
- s3.1 Germanic tribes invasion photograph (px) — **FP**: cabaña de pescador no relacionada
- s4.2 fall of Roman Empire illustration (px) — **FP**: retrato genérico de mujer romana

> NOTA: `SYSTEMIC_FAILURE` aquí es exclusivamente de la ETAPA de assets (acceptance/cobertura). El script/VisualPlan de este tema fue sano y genérico; NO es fallo de comprensión de dominio.

**5) Pulpos — 5 resueltos (CR 3, CU 1, FP 1) → USABLE_WITH_LIMITATIONS**
- s2.1 camouflage reef (px) — CR
- s2.2 hiding in coral (px) — CR
- s3.1 tentacles catching prey (px) — **FP**: pulpo colgado/muerto, no representa la acción de caza pedida
- s4.1 blue ringed octopus venom (px) — CR
- s5.1 underwater environment (px) — CU

**6) Volcán — 6 resueltos (CR 4, CU 2, FP 0) → HEALTHY**
- s1.1 eruption lava flow (px) — CR
- s2.2 earth crust diagram (px) — CU
- s3.2 volcano explosion (px) — CR
- s4.1 volcanic ash (px) — CR
- s4.2 lava flow (px) — CR
- s5.1 volcano landscape (px) — CU

**7) Videojuegos 3D — 2 resueltos (CR 0, CU 2, FP 0) → USABLE_WITH_LIMITATIONS**
- s3.1 PlayStation N64 comparison (px) — CU (joystick/controlador genérico)
- s4.1 modern 3D immersive (px) — CU (VR headset)
- Limitación principal: cobertura de provider (2/10), no planificación upstream.

**8) Hipoteca — 4 resueltos (CR 2, CU 2, FP 0) → USABLE_WITH_LIMITATIONS**
- s1.1 mortgage signing (px) — CR
- s2.1 mortgage office agent (px) — CU
- s3.1 interest calculator (px) — CR
- s4.1 amortization chart (px) — CU: el gráfico genérico de analítica/laptop es coarse para amortización, pero NO es un falso positivo obvio tras inspección de píxeles.

---


## 4. Segmentos NO resueltos (status persistido) + causa

Distribución por tema (status persistido en metadata):

| Tema | NO_RESULTS | DOWNLOAD_FAILED |
|------|-----------|-----------------|
| Aurora | 1 | 0 |
| Porsche | 2 | 0 |
| Spring Boot | 7 | 0 |
| Roma | 4 | 1 |
| Pulpos | 4 | 0 |
| Volcán | 3 | 0 |
| Videojuegos | 8 | 0 |
| Hipoteca | 2 | 0 |

- Los `NO_RESULTS` tienen razón persistida "no Pixabay candidate downloaded successfully" / "no candidate passed minimum filters". El metadata persistido NO conserva `semanticRejections` (gap conocido de Fase 1), por lo que NO se puede distinguir "provider no devolvió candidatos" de "el gate semántico rechazó todos". → **causa = `UNRESOLVED_CAUSE_UNCERTAIN`** (contrato B). NO se sondea ni se repite búsqueda.
- `DOWNLOAD_FAILED` (Roma, 1) es claramente fallo de descarga (no semántico).

---

## 5. Observaciones CORE vs SUPPLY/COVERAGE

### CORE (evidencia directa)
- **`SEMANTIC_GATE_FALSE_POSITIVE` (probables, pendientes de confirmación visual):**
  - Porsche — vector de pista de tenis aceptado como "sports cars history diagram" (s5.2).
  - Spring Boot — ilustración genérica de workflow aceptada como "Spring Boot project structure diagram" (s3.1).
  - Roma — cabaña de pescador aceptada como "Germanic tribes invasion" (s3.1); retrato romano aceptado como "fall of Roman Empire" (s4.2).
  - Hipoteca — gráfico de navegador aceptado como "amortization chart graph" (s4.1).
  - **Se repite en 4 dominios NO relacionados** (automoción, software, historia, finanzas).
- **`QUERY_GEN_FAILURE`:** Ninguno. 100% de queries `VALID`/concretas en los 8 dominios.
- **`VISUAL_PLAN_FAILURE`:** Ninguno. VisualPlans válidos y alineados en los 8 dominios.

### SUPPLY / COVERAGE (evidencia directa)
- **`PROVIDER_COVERAGE_FAILURE`:** cobertura pobre en varias familias: Spring Boot (7/10 unres), Videojuegos (8/10 unres), Roma (5/9), Pulpos (4/9). Plus Pixabay fue el provider que más resolvió; Wikimedia aportó resueltos solo en Aurora y Porsche.
- **`UNRESOLVED_CAUSE_UNCERTAIN`:** los `NO_RESULTS` (no se puede distinguir causa sin `semanticRejections`).
- **`ACCEPTABLE_ASSETS_PARTIAL`:** Aurora, Volcán, Pulpos, Hipoteca, Porsche (ratios 0.56–0.86) con la mayoría de los resueltos on-topic por metadata → parciales aceptables dentro de lo esperable.

---

## 6. Clasificación final por tema (tras revisión visual de píxeles)

Clasificaciones FINALES con inspección visual externa completa (ya no provisionales).

| # | Tema | Clasificación final | CR/CU/FP | Base |
|---|------|---------------------|----------|------|
| 1 | Aurora | `USABLE_WITH_LIMITATIONS` | 2/2/2 | 2 assets inutilizables (antena nocturna, GIF en blanco) |
| 2 | Porsche | `USABLE_WITH_LIMITATIONS` | 3/3/2 | ilustración de modelo moderno + pista de tenis |
| 3 | Spring Boot | `USABLE_WITH_LIMITATIONS` | 1/1/1 | workflow genérico como "project structure" |
| 4 | Roma | `SYSTEMIC_FAILURE` (capa de assets) | 1/1/2 | 2/4 off-topic obvios (cabaña, retrato) |
| 5 | Pulpos | `USABLE_WITH_LIMITATIONS` | 3/1/1 | pulpo colgado no representa la acción de caza |
| 6 | Volcán | `HEALTHY` | 4/2/0 | sin falsos positivos |
| 7 | Videojuegos | `USABLE_WITH_LIMITATIONS` | 0/2/0 | cobertura 2/10 (provider), no upstream |
| 8 | Hipoteca | `USABLE_WITH_LIMITATIONS` | 2/2/0 | coarse pero sin FP obvio tras píxeles |

Ningún tema falla en script/VisualPlan: la capa core es genérica y sana en los 8 dominios. `SYSTEMIC_FAILURE` de Roma es exclusivamente de la ETAPA de assets (aceptación de candidatos off-topic), no de comprensión de dominio.

---

## 7. Decisión agregada

**`YELLOW`**

Interpretación (contrato del change):
- Script/VisualPlan sano y topic-agnostic: sin patrón `QUERY_GEN_FAILURE`, sin patrón `VISUAL_PLAN_FAILURE`.
- Fallo CORE repetido en la ACEPTACIÓN de candidatos downstream (fidelidad visual/semántica): 8 `FALSE_POSITIVE_OR_UNUSABLE` sobre 38 resueltos, repartidos en ≥4 dominios no relacionados.
- La cobertura de provider también es limitada (especialmente software/videojuegos y conceptos difíciles de ilustrar con stock), pero permanece como SUPPLY, no corrupción de arquitectura.

Totales finales de revisión visual: 38 resueltos → **16 `CLEARLY_RELEVANT` / 14 `COARSE_BUT_USABLE` / 8 `FALSE_POSITIVE_OR_UNUSABLE`**.

---

## 8. Respuestas a las 7 preguntas de análisis

**1. ¿El LLM produce VisualPlans útiles en dominios no relacionados?**
Sí. Los 8 temas produjeron script + VisualPlan estructuralmente válidos en attempt 1 (retries 0), con queries 100% `VALID`/concretas, subjects apropiados y `assetPreferences` razonables. La capa script/VisualPlan se comporta genérica y uniformemente.

**2. ¿Los malos resultados vienen de la generación de queries (upstream) o de la cobertura de provider (downstream)?**
Del downstream (cobertura de provider + gate de aceptación). No hay `QUERY_GEN_FAILURE` (todas las queries concretas y VALID). Los no resueltos son `NO_RESULTS` (cobertura) o `DOWNLOAD_FAILED`; los resueltos incorrectos pasan el gate por solapamiento léxico sin garantía de que los píxeles representen la intención. El bootstrap `FAIL` de 3 jobs no impactó (telemetría no bloqueante).

**3. ¿Aparecen falsos positivos semánticos repetidos en dominios no relacionados, o el caso Smosh fue aislado?**
Repetidos y confirmados visualmente. 8 assets `FALSE_POSITIVE_OR_UNUSABLE` en 5 temas (Aurora 2, Porsche 2, Spring Boot 1, Roma 2, Pulpos 1) de dominios no relacionados. El caso Smosh NO fue aislado; es un síntoma recurrente de la etapa de assets.

**4. ¿Los temas abstractos (Spring Boot, hipoteca) son materialmente peores que los de tema visual concreto?**
Peores en COBERTURA de assets, no en calidad de script/VisualPlan. Spring Boot (3/10) y Videojuegos (2/10) tienen ratios bajos; hipoteca (4/6). La abstracción dificulta encontrar stock concreto, pero no degradó la generación de queries ni el plan. La tasa de FP no es peor en abstractos (Aurora, Porsche, Roma y Pulpos — temas concretos — acumulan 7 de los 8 FP).

**5. ¿Hay evidencia de que la arquitectura dejó de ser agnóstica de tema?**
No. No hay ramas de dominio; los vocabularios léxicos (filler/weak/stop/specificity) son genéricos; los 8 dominios recibieron planes válidos. La arquitectura sigue siendo topic-agnostic.

**6. ¿Asset-entity-fidelity está justificado por evidencia repetida, o debe seguir en pausa?**
**Conclusión de diseño (cambiada tras la inspección de píxeles):** la evidencia muestra que el problema es MÁS amplio que la fidelidad de entidad nombrada. Los fallos cubren entidades, conceptos, ACCIONES y semántica de escena (`sports cars history`→pista de tenis; `Germanic tribes invasion`→cabaña; `octopus catching prey`→pulpo colgado; `aurora solar particles`→instalación nocturna). Por tanto `asset-entity-fidelity` permanece como EVIDENCIA DE INVESTIGACIÓN SOLO y NO es la dirección de implementación. `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS` NO es el próximo implementation aprobado. El futuro cambio genérico se registra como **`asset-visual-semantic-fidelity`** (ver §10).

**7. ¿Cuál es la dirección siguiente más justificada (única)?**
La siguiente dirección más justificada es **`asset-visual-semantic-fidelity`**: una validación semántico-visual genérica de segunda etapa basada en los PÍXELES de la imagen (provider-agnostic), manteniendo el gate de metadata actual como primera etapa barata. La evidencia demuestra que la relevancia léxica por metadata es un filtro previo útil pero no puede probar que los píxeles representen la intención visual pedida. Secundariamente (dirección de producto separada): estrategia de provider con fallback search-vs-generation para los conceptos que los bancos de stock no cubren.

---

## 9. Paths de assets para revisión visual externa (por tema)

- **1 Aurora:** `data/videos/cmo-2026-08-17-233901/assets/{scene_001_seg_001.png, scene_001_seg_002.jpg, scene_002_seg_001.jpg, scene_003_seg_001.png, scene_004_seg_001.jpg, scene_005_seg_001.gif}`
- **2 Porsche:** `data/videos/la-2026-08-17-234123/assets/{scene_001_seg_001.jpg, scene_001_seg_002.jpg, scene_002_seg_001.jpg, scene_002_seg_002.png, scene_003_seg_001.jpg, scene_004_seg_001.jpg, scene_005_seg_001.jpg, scene_005_seg_002.png}`
- **3 Spring Boot:** `data/videos/cmo-2026-08-17-234325/assets/{scene_001_seg_002.jpg, scene_002_seg_002.jpg, scene_003_seg_001.png}`
- **4 Roma:** `data/videos/por-2026-08-17-234531/assets/{scene_001_seg_002.jpg, scene_002_seg_002.png, scene_003_seg_001.jpg, scene_004_seg_002.png}`
- **5 Pulpos:** `data/videos/cmo-2026-08-17-234735/assets/{scene_002_seg_001.jpg, scene_002_seg_002.jpg, scene_003_seg_001.jpg, scene_004_seg_001.jpg, scene_005_seg_001.jpg}`
- **6 Volcán:** `data/videos/qu-2026-08-17-234954/assets/{scene_001_seg_001.jpg, scene_002_seg_002.png, scene_003_seg_002.jpg, scene_004_seg_001.jpg, scene_004_seg_002.jpg, scene_005_seg_001.jpg}`
- **7 Videojuegos:** `data/videos/cmo-2026-08-17-235250/assets/{scene_003_seg_001.jpg, scene_004_seg_001.jpg}`
- **8 Hipoteca:** `data/videos/cmo-2026-08-17-235456/assets/{scene_001_seg_001.jpg, scene_002_seg_001.jpg, scene_003_seg_001.jpg, scene_004_seg_001.png}`

---

## 10. Conclusiones de diseño y cambios futuros registrados

### Conclusión de genericity
El pipeline es genérico y topic-agnostic en su capa core: script + VisualPlan (LLM) funcionan uniformemente en los 8 dominios sin ramas de dominio, queries 100% `VALID`, retries 0. La arquitectura NO está corrompida. Decisión agregada: **YELLOW**.

### Conclusión de fidelidad downstream
La evidencia visual muestra que el problema NO es solo de fidelidad de entidad nombrada: los fallos cubren entidades, conceptos, acciones y semántica de escena. La relevancia léxica por metadata es un filtro previo útil y barato, pero NO puede probar que los píxeles de la imagen representen la intención visual pedida. 8 de 38 assets resueltos resultaron `FALSE_POSITIVE_OR_UNUSABLE` repartidos en 5 dominios no relacionados.

### Conclusión de cobertura de provider
La cobertura de search providers (Wikimedia/Pixabay) no cubre todas las necesidades genéricas de VisualPlan (software, videojuegos, conceptos difíciles de ilustrar con stock). Permanecen como SUPPLY, separados de la arquitectura semántica.

### Cambio futuro registrado: `asset-visual-semantic-fidelity` (NO diseñado ahora)
- **Problem statement:** la relevancia semántica por metadata (léxica) es un coarse pre-filter válido pero no puede garantizar que los píxeles representen la intención visual pedida; los fallos incluyen entidades, conceptos, acciones y semántica de escena.
- **Plan futuro:** investigar una validación semántico-visual genérica de SEGUNDA ETAPA basada en los píxeles de la imagen (provider-agnostic), conservando el gate de metadata actual como primera etapa barata.
- **NO implementar en este cambio.** `deterministic_anchor_coverage_v3` / `FORM_OR_MEDIUM_TERMS` NO es la dirección aprobada.

### Estado de `asset-entity-fidelity`
Permanece como EVIDENCIA DE INVESTIGACIÓN SOLO (pausado). NO es la dirección de implementación activa. NO reemplaza al cambio futuro `asset-visual-semantic-fidelity`.

### Dirección de producto separada (registrada, no diseñada)
Los providers de búsqueda por sí solos no cubren todas las necesidades genéricas de VisualPlan; un fallback search-vs-generation es una dirección de producto separada.
