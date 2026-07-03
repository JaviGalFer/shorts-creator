#!/usr/bin/env python3


def normalize(t: str) -> str:
    import re
    return re.sub(r'\s+', ' ', t.lower().strip()).strip(".,!?;: \"'")


def validate_scene_timing_coverage(scene_timings: list[dict], audio_duration_sec: float) -> dict:
    errors = []
    warnings = []
    total_covered = 0.0

    for i, st in enumerate(scene_timings):
        start = st.get("startSec", 0)
        end = st.get("endSec", 0)
        dur = end - start

        if dur <= 0:
            errors.append(f"sceneTimings[{i}] scene={st['sceneNumber']}: duration={dur} <= 0")
        total_covered += dur

        if i > 0:
            prev = scene_timings[i - 1]
            if start < prev["endSec"]:
                errors.append(
                    f"sceneTimings[{i}] scene={st['sceneNumber']}: start={start} < "
                    f"previous end={prev['endSec']} (overlap)"
                )

    coverage_pct = (total_covered / audio_duration_sec * 100) if audio_duration_sec > 0 else 0
    if coverage_pct < 98:
        errors.append(f"sceneTiming coverage {coverage_pct:.1f}% < 98%")
    elif coverage_pct < 99:
        warnings.append(f"sceneTiming coverage {coverage_pct:.1f}% ≥98% but <99%")

    return {
        "coveragePercent": round(coverage_pct, 1),
        "totalCoveredSec": round(total_covered, 3),
        "totalDurationSec": round(audio_duration_sec, 3),
        "overlaps": len([e for e in errors if "overlap" in e]),
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


def validate_cue_text(cues_by_scene: dict[int, list[dict]],
                      narration_units: list[dict]) -> list[str]:
    errors = []
    cue_text = " ".join(
        c["text"] for cues in cues_by_scene.values() for c in cues
    )
    nar_text = " ".join(u["text"] for u in narration_units)

    if normalize(cue_text) != normalize(nar_text):
        errors.append("Cue text does not match narration text")
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

    all_cues = []
    for cues in cues_by_scene.values():
        all_cues.extend(cues)
    cue_integrity_errors = validate_cue_integrity(all_cues, audio_duration_sec)

    remap_errors = []
    if remapped_cues is not None:
        remap_errors = validate_remapped_cues(remapped_cues)

    all_errors = coverage["errors"] + cue_scene_errors + cue_text_errors + cue_integrity_errors + remap_errors
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
        "remapValidation": {
            "errors": remap_errors,
            "totalRemapped": len(remapped_cues) if remapped_cues else 0,
        },
    }
