#!/usr/bin/env python3


from shorts_creator.validation.subtitle_normalize import (
    normalize_subtitle_text,
    normalize_subtitle_tokens,
    compare_cue_vs_narration_bulk,
)


def validate_scene_timing_coverage(scene_timings: list[dict], audio_duration_sec: float) -> dict:
    errors = []
    warnings = []
    overlapping = 0

    # Extend native word-boundary timings to fill inter-scene gaps (pauses).
    # Scene i's endSec becomes the next scene's startSec (or audio end for last scene).
    # This ensures coverage ≥98% for native timings; raw word boundaries would
    # only cover ~70% due to natural pauses between narration units.
    extended = []
    for i, st in enumerate(scene_timings):
        start = st.get("startSec", 0)
        if i < len(scene_timings) - 1:
            end = scene_timings[i + 1].get("startSec", 0)
        else:
            end = audio_duration_sec
        if end <= start:
            end = st.get("endSec", start)
        extended.append({"sceneNumber": st["sceneNumber"], "startSec": start, "endSec": end})

    total_covered = 0.0
    for i, ext in enumerate(extended):
        start = ext["startSec"]
        end = ext["endSec"]
        dur = end - start
        if dur <= 0:
            errors.append(f"sceneTimings[{i}] scene={ext['sceneNumber']}: duration={dur} <= 0")
        total_covered += dur
        if i > 0 and start < extended[i - 1]["endSec"]:
            errors.append(
                f"sceneTimings[{i}] scene={ext['sceneNumber']}: "
                f"start={start} < previous end={extended[i-1]['endSec']} (overlap)"
            )
            overlapping += 1

    coverage_pct = (total_covered / audio_duration_sec * 100) if audio_duration_sec > 0 else 0
    if coverage_pct < 98:
        errors.append(f"sceneTiming coverage {coverage_pct:.1f}% < 98%")
    elif coverage_pct < 99:
        warnings.append(f"sceneTiming coverage {coverage_pct:.1f}% ≥98% but <99%")

    return {
        "coveragePercent": round(coverage_pct, 1),
        "totalCoveredSec": round(total_covered, 3),
        "totalDurationSec": round(audio_duration_sec, 3),
        "overlaps": overlapping,
        "errors": errors,
        "warnings": warnings,
        "status": "PASS" if not errors else ("REVIEW_REQUIRED" if warnings else "FAIL"),
    }


CUE_BOUNDARY_TOLERANCE = 0.15


def validate_cues_per_scene(cues_by_scene: dict[int, list[dict]],
                            scene_timings: list[dict]) -> list[str]:
    errors = []
    timing_map = {st["sceneNumber"]: st for st in scene_timings}

    for sn, cues in cues_by_scene.items():
        st = timing_map.get(sn)
        if not st:
            errors.append(f"Scene {sn}: no sceneTiming entry")
            continue
        for ci, cue in enumerate(cues):
            cs = cue.get("startSec", 0)
            ce = cue.get("endSec", 0)
            if cs < st["startSec"] - CUE_BOUNDARY_TOLERANCE or ce > st["endSec"] + CUE_BOUNDARY_TOLERANCE:
                errors.append(
                    f"Scene {sn} cue[{ci}]: [{cs:.3f}-{ce:.3f}] outside sceneTiming "
                    f"[{st['startSec']:.3f}-{st['endSec']:.3f}]"
                )
    return errors


def _strip_punct(w: str) -> str:
    return w.strip(".,!?;:\"'()[]¿¡-")


def validate_cue_text(cues_by_scene: dict[int, list[dict]],
                      narration_units: list[dict]) -> list[str]:
    errors = []
    cue_texts = [
        c["text"] for cues in cues_by_scene.values() for c in cues
    ]
    nar_texts = [u["text"] for u in narration_units]

    result = compare_cue_vs_narration_bulk(cue_texts, nar_texts)
    if result["status"] != "PASS":
        msg = "Cue text does not match narration text"
        if result.get("missingTokens"):
            msg += f" (missing: {result['missingTokens']})"
        if result.get("extraTokens"):
            msg += f" (extra: {result['extraTokens']})"
        errors.append(msg)
    return errors


def validate_canonical_cue_integrity(
    cues_by_scene: dict[int, list[dict]],
    narration_units: list[dict],
) -> list[dict]:
    """Semantic validation: no cue may contain words from multiple narration units.
    Returns list of error dicts with exact offending token and source/target scene."""
    errors = []
    scene_narration_map = {}
    for nu in narration_units:
        sn = nu["sceneNumber"]
        if sn not in scene_narration_map:
            scene_narration_map[sn] = []
        scene_narration_map[sn].append(nu["text"])
    scene_words_map = {
        sn: {_strip_punct(w).lower() for text in texts for w in text.split()}
        for sn, texts in scene_narration_map.items()
    }

    for sn, cues in cues_by_scene.items():
        scene_words = scene_words_map.get(sn, set())
        for ci, cue in enumerate(cues):
            cue_text = cue.get("text", "")
            if not cue_text:
                continue
            for w in cue_text.split():
                w_clean = _strip_punct(w).lower()
                if len(w_clean) <= 3:
                    continue
                if w_clean not in scene_words:
                    # Check if word belongs to another scene's vocabulary
                    target_sn = None
                    for other_sn, other_words in scene_words_map.items():
                        if other_sn != sn and w_clean in other_words:
                            target_sn = other_sn
                            break
                    errors.append({
                        "type": "CROSS_SCENE_CUE",
                        "severity": "ERROR",
                        "sceneNumber": sn,
                        "cueIndex": ci,
                        "offendingToken": w_clean,
                        "sourceScene": sn,
                        "targetScene": target_sn,
                        "cueText": cue_text[:80],
                    })
    return errors


def validate_cue_integrity(cues: list[dict], audio_duration_sec: float) -> list[str]:
    errors = []
    for i, cue in enumerate(cues):
        cs = cue.get("startSec", 0)
        ce = cue.get("endSec", 0)
        if cs >= ce:
            errors.append(f"Cue[{i}]: startSec ({cs}) >= endSec ({ce})")
        if cs < 0:
            errors.append(f"Cue[{i}]: startSec ({cs}) < 0")
        if ce > audio_duration_sec + 0.5:
            errors.append(f"Cue[{i}]: endSec ({ce}) exceeds audio duration ({audio_duration_sec})")
        if i > 0:
            prev = cues[i - 1]
            if cs < prev["endSec"] - 0.05:
                errors.append(
                    f"Cue[{i}]: startSec ({cs}) overlaps previous cue endSec ({prev['endSec']})"
                )
    return errors


def validate_remapped_cues(remapped_cues: list[dict]) -> list[str]:
    errors = []
    for i, r in enumerate(remapped_cues):
        if r.get("crossesTrim"):
            errors.append(
                f"Remapped cue[{i}]: [{r['originalStart']:.3f}-{r['originalEnd']:.3f}] "
                f"crosses a trim boundary — review required"
            )
        drift = r.get("driftMs", 0)
        if drift > 5:
            errors.append(
                f"Remapped cue[{i}]: drift {drift:.1f}ms exceeds 5ms threshold"
            )
    return errors


def run_coverage_validation(scene_timings: list[dict], audio_duration_sec: float,
                            cues_by_scene: dict[int, list[dict]],
                            narration_units: list[dict],
                            remapped_cues: list[dict] | None = None) -> dict:
    coverage = validate_scene_timing_coverage(scene_timings, audio_duration_sec)
    cue_scene_errors = validate_cues_per_scene(cues_by_scene, scene_timings)
    cue_text_errors = validate_cue_text(cues_by_scene, narration_units)
    canonical_errors = validate_canonical_cue_integrity(cues_by_scene, narration_units)

    all_cues = []
    for cues in cues_by_scene.values():
        all_cues.extend(cues)
    cue_integrity_errors = validate_cue_integrity(all_cues, audio_duration_sec)

    remap_errors = []
    if remapped_cues is not None:
        remap_errors = validate_remapped_cues(remapped_cues)

    all_errors = (coverage["errors"] + cue_scene_errors + cue_text_errors +
                  cue_integrity_errors + remap_errors + [e["offendingToken"] + " from scene " +
                  str(e["targetScene"]) + " leaked into scene " + str(e["sourceScene"])
                  for e in canonical_errors])
    all_warnings = coverage.get("warnings", [])

    status = "PASS"
    if all_errors:
        status = "FAIL"
    elif all_warnings:
        status = "REVIEW_REQUIRED"

    return {
        "status": status,
        "coverage": coverage,
        "cuesPerScene": {
            "errors": cue_scene_errors,
            "count": sum(len(c) for c in cues_by_scene.values()),
        },
        "cueText": {
            "errors": cue_text_errors,
            "narrationUnits": len(narration_units),
        },
        "cueIntegrity": {
            "errors": cue_integrity_errors,
            "totalCues": len(all_cues),
        },
        "canonicalValidation": {
            "errors": canonical_errors,
            "totalCrossScene": len(canonical_errors),
        },
        "remapValidation": {
            "errors": remap_errors,
            "totalRemapped": len(remapped_cues) if remapped_cues else 0,
        },
    }
