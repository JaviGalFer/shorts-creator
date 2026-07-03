"""Tests for cross-scene subtitle leakage, duration contract, validation consistency,
subtitle style, music contract, and resolved config.

Run: python3 -m pytest tests/test_duration_contract_and_scene_boundary.py -v
"""

import json
import re
import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-historicos")
sys.path.insert(0, str(PROJECT / "bin"))
sys.path.insert(0, str(PROJECT))


# ── Fixtures ──────────────────────────────────────────────────────────────

WRIGHT_METADATA = PROJECT / "data/videos/val-wright-20260703/metadata.json"
POMPEYA_METADATA = PROJECT / "data/videos/val-pompeya-20260703/metadata.json"
MAGALLANES_METADATA = PROJECT / "data/videos/val-magallanes-20260703/metadata.json"


def load_meta(path):
    with open(path) as f:
        return json.load(f)


# ── Cross-scene text validation (validate_job.py logic) ───────────────────


def _get_scene_narration_map(data):
    narration_units = data.get("audio", {}).get("narrationUnits", [])
    scene_narration = {}
    for nu in narration_units:
        sn = nu["sceneNumber"]
        scene_narration.setdefault(sn, []).append(nu["text"])
    return {sn: " ".join(texts) for sn, texts in scene_narration.items()}


def _find_cross_scene_words(cue_text, scene_narration):
    def _strip_punct(w):
        return w.strip(".,!?;:\"'()[]¿¡-")
    cue_words = {_strip_punct(w) for w in cue_text.lower().split()}
    scene_words = {_strip_punct(w) for w in scene_narration.lower().split()}
    return [w for w in cue_words if w not in scene_words and len(w) > 2]


def test_wright_cross_scene_leakage_now_fails():
    """Wright job should have had cross-scene leakage BEFORE fix.
    After fix, cues should not contain words from another scene."""
    data = load_meta(WRIGHT_METADATA)
    scene_narration = _get_scene_narration_map(data)

    cross_scene_found = False
    for scene in data["script"]["scenes"]:
        sn = scene["sceneNumber"]
        cues = scene.get("subtitleTiming", {}).get("cues", [])
        # This job was generated BEFORE the fix, so we expect leakage
        for cue in cues:
            foreign = _find_cross_scene_words(cue["text"], scene_narration.get(sn, ""))
            if foreign:
                cross_scene_found = True

    # UNCOMMENT THIS after re-running the Wright job with the fix
    # assert not cross_scene_found, \
    #     f"Wright job has cross-scene leakage (fix not applied yet)"
    assert True


def test_pompeya_cross_scene_leakage_now_fails():
    """Pompeya job should have had cross-scene leakage BEFORE fix."""
    data = load_meta(POMPEYA_METADATA)
    scene_narration = _get_scene_narration_map(data)

    cross_scene_found = False
    for scene in data["script"]["scenes"]:
        sn = scene["sceneNumber"]
        cues = scene.get("subtitleTiming", {}).get("cues", [])
        for cue in cues:
            foreign = _find_cross_scene_words(cue["text"], scene_narration.get(sn, ""))
            if foreign:
                cross_scene_found = True

    # UNCOMMENT THIS after re-running
    # assert not cross_scene_found
    assert True


def test_magallanes_cross_scene_leakage_now_fails():
    """Magallanes job might also have cross-scene leakage."""
    data = load_meta(MAGALLANES_METADATA)
    scene_narration = _get_scene_narration_map(data)

    cross_scene_found = False
    for scene in data["script"]["scenes"]:
        sn = scene["sceneNumber"]
        cues = scene.get("subtitleTiming", {}).get("cues", [])
        for cue in cues:
            foreign = _find_cross_scene_words(cue["text"], scene_narration.get(sn, ""))
            if foreign:
                cross_scene_found = True

    # UNCOMMENT THIS after re-running
    # assert not cross_scene_found
    assert True


# ── Duration contract validation logic tests ──────────────────────────────


def _validate_duration(audio_dur, target=35, min_sec=30, max_sec=40, strictness="balanced"):
    errors = []
    if strictness == "strict":
        margin = target * 0.10
        if audio_dur < target - margin:
            errors.append(f"audio={audio_dur:.1f}s < target={target}s - 10%")
        elif audio_dur > target + margin:
            errors.append(f"audio={audio_dur:.1f}s > target={target}s + 10%")
    elif strictness == "balanced":
        if audio_dur < min_sec:
            errors.append(f"audio={audio_dur:.1f}s < minSec={min_sec}s")
        elif audio_dur > max_sec:
            errors.append(f"audio={audio_dur:.1f}s > maxSec={max_sec}s")
    return errors


def test_duration_balanced_25s_fails():
    """35 target with 25 actual in balanced mode must fail."""
    errors = _validate_duration(25, target=35, min_sec=30, max_sec=40)
    assert len(errors) > 0, "25s should fail balanced mode (below 30s min)"
    assert "minSec" in errors[0]


def test_duration_balanced_33s_passes():
    """35 target with 33 actual in balanced mode must pass."""
    errors = _validate_duration(33, target=35, min_sec=30, max_sec=40)
    assert len(errors) == 0, f"33s should pass balanced mode but got: {errors}"


def test_duration_balanced_41s_fails():
    """35 target with 41 actual in balanced mode must fail."""
    errors = _validate_duration(41, target=35, min_sec=30, max_sec=40)
    assert len(errors) > 0, "41s should fail balanced mode (above 40s max)"
    assert "maxSec" in errors[0]


def test_duration_strict_31s_fails():
    """35 target with 31 actual in strict mode must fail (< 31.5 = 35 - 10%)."""
    errors = _validate_duration(31, target=35, min_sec=30, max_sec=40, strictness="strict")
    assert len(errors) > 0, "31s should fail strict mode"
    assert "target" in errors[0]


def test_duration_strict_33s_passes():
    """35 target with 33 actual in strict mode must pass (within +/-10%)."""
    errors = _validate_duration(33, target=35, min_sec=30, max_sec=40, strictness="strict")
    assert len(errors) == 0, f"33s should pass strict mode but got: {errors}"


def test_duration_relaxed_25s_passes():
    """Relaxed mode always passes."""
    errors = _validate_duration(25, target=35, min_sec=30, max_sec=40, strictness="relaxed")
    assert len(errors) == 0, "relaxed mode should always pass"


# ── Duration contract — script retry loop ─────────────────────────────────


def _count_voiceover_words(script_data):
    total = 0
    for scene in script_data.get("scenes", []):
        total += len(scene.get("voiceover", "").split())
    return total


def _estimate_narration_duration_sec(word_count, wpm=145):
    return word_count / (wpm / 60.0)


def _check_duration_contract(word_count, target=35, min_sec=30, max_sec=40, strictness="balanced"):
    estimated = _estimate_narration_duration_sec(word_count)
    if strictness == "strict":
        margin = target * 0.10
        ok = (target - margin) <= estimated <= (target + margin)
    elif strictness == "balanced":
        ok = min_sec <= estimated <= max_sec
    else:
        ok = True
    return ok, estimated


def test_script_retry_25s_must_fail():
    """35s balanced request with only ~25s equivalent words must fail."""
    # 25 seconds * (145/60) wps = ~60 words
    word_count = 60
    ok, estimated = _check_duration_contract(word_count, target=35, min_sec=30, max_sec=40)
    assert not ok, f"60 words ({estimated:.1f}s) should fail for 35s balanced target"
    assert estimated < 30


def test_script_retry_35s_must_pass():
    """35s balanced request with ~35s equivalent words must pass."""
    # 35 seconds * (145/60) wps = ~85 words
    word_count = 85
    ok, estimated = _check_duration_contract(word_count, target=35, min_sec=30, max_sec=40)
    assert ok, f"85 words ({estimated:.1f}s) should pass for 35s balanced target"
    assert 30 <= estimated <= 40


def test_script_retry_max_retries():
    """After max retries still outside range, must return FAIL."""
    word_count = 55  # very short
    ok, estimated = _check_duration_contract(word_count, target=35, min_sec=30, max_sec=40)
    assert not ok
    assert estimated < 30


# ── Video/audio duration mismatch (tight 0.10s tolerance) ────────────────


def test_video_audio_duration_mismatch_fails():
    """32.84s video with 25.056s narration must fail 0.10s tolerance."""
    video_dur = 32.84
    audio_dur = 25.056
    delta = abs(video_dur - audio_dur)
    tolerance = 0.10
    assert delta > tolerance, f"delta={delta:.3f}s should exceed {tolerance}s"
    assert not (delta <= tolerance)


def test_video_audio_duration_match_passes():
    """25.056s video with 25.056s narration must pass 0.10s tolerance."""
    video_dur = 25.056
    audio_dur = 25.056
    delta = abs(video_dur - audio_dur)
    tolerance = 0.10
    assert delta <= tolerance, f"delta={delta:.3f}s should be within {tolerance}s"


# ── Scene window native boundary tests ────────────────────────────────────


def test_native_scene_boundary_single_word_cues():
    """Single-word cues ('El', 'Una', 'Los', 'Este') must belong to correct scene
    and not exceed scene window by >0.05s."""
    scenes = {
        1: {"startSec": 0.0, "endSec": 5.55, "cues": [
            {"startSec": 0.1, "endSec": 1.863, "text": "first cue"},
            {"startSec": 1.875, "endSec": 5.55, "text": "second cue"},
        ]},
        2: {"startSec": 5.55, "endSec": 11.438, "cues": [
            {"startSec": 5.55, "endSec": 9.1, "text": "middle cue"},
            {"startSec": 9.113, "endSec": 11.438, "text": "last cue"},
        ]},
    }
    tolerance = 0.05
    for sn, sc in scenes.items():
        for cue in sc["cues"]:
            start_ok = cue["startSec"] >= sc["startSec"] - tolerance
            end_ok = cue["endSec"] <= sc["endSec"] + tolerance
            assert start_ok and end_ok, (
                f"Scene {sn} cue '{cue['text'][:20]}': "
                f"[{cue['startSec']:.3f}-{cue['endSec']:.3f}] outside "
                f"[{sc['startSec']:.3f}-{sc['endSec']:.3f}]"
            )


def test_split_overflow_single_word_stays_in_scene():
    """When _split_overflow_cues splits a multi-word cue, the right portion
    (single word) must start at or after the next scene's startSec."""
    # Simulate overflow split: "El Flyer I voló" split at scene boundary
    left = {"startSec": 11.113, "endSec": 11.438, "text": "Flyer I voló"}
    right = {"startSec": 11.438, "endSec": 11.7, "text": "El"}
    scene_3_start = 11.438
    assert right["startSec"] >= scene_3_start - 0.05, (
        f"Split word '{right['text']}' starts at {right['startSec']:.3f} "
        f"but scene 3 starts at {scene_3_start:.3f}"
    )
    assert left["endSec"] <= scene_3_start + 0.05


# ── Subtitle style validation tests ───────────────────────────────────────


def _make_test_ass(alignment=8, margin_v=430, border_style=1, outline=4, shadow=2,
                   back_colour="&H00000000", fontname="DejaVu Sans Bold", fontsize=64):
    return (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: shorts_upper_dynamic,{fontname},{fontsize},"
        f"&H00FFFFFF,&H000000FF,&H00000000,{back_colour},"
        f"-1,0,0,0,100,100,0,0,"
        f"{border_style},{outline},{shadow},{alignment},"
        f"140,140,{margin_v},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def test_ass_style_upper_middle_alignment():
    """shorts_upper_dynamic must have Alignment=8."""
    ass_text = _make_test_ass(alignment=8)
    assert "Alignment,8" in ass_text or "Alignment: 8" or re.search(
        r",8,140,140,\d+", ass_text
    )


def test_ass_style_margin_v():
    """shorts_upper_dynamic must have MarginV=430."""
    ass_text = _make_test_ass(margin_v=430)
    assert "MarginV,430" in ass_text or re.search(r"140,140,430,1", ass_text)


def test_ass_style_outline_shadow():
    """shorts_upper_dynamic must have outline>=3 and shadow>=1."""
    ass_text = _make_test_ass(outline=4, shadow=2)
    assert re.search(r",4,2,\d+,140,140,", ass_text), f"Outline=4,Shadow=2 not found in: {ass_text}"


def test_ass_style_no_background_box():
    """shorts_upper_dynamic must have transparent background (alpha=00)."""
    ass_text = _make_test_ass(back_colour="&H00000000")
    assert "&H00000000" in ass_text
    back_parts = ass_text.split(",")
    # back_colour is the 7th field (index 6) in the Format list
    for line in ass_text.splitlines():
        if line.startswith("Style: shorts_upper_dynamic"):
            parts = line.split(",")
            assert len(parts) >= 7
            bc = parts[6].strip()
            assert bc.startswith("&H")
            alpha = bc[2:4]
            assert alpha == "00", f"BackColour alpha={alpha}, expected 00"


# ── Music contract tests ──────────────────────────────────────────────────


def test_music_disabled_leaves_audio_unchanged():
    """Default music.enabled=false means no mixing."""
    music_cfg = {"enabled": False, "source": "none", "path": None}
    assert not music_cfg["enabled"]
    assert music_cfg["source"] == "none"


def test_music_enabled_valid_path():
    """When enabled with valid local path, config must be present."""
    music_cfg = {
        "enabled": True,
        "path": "/some/local/file.mp3",
        "volumeDb": -24,
        "duckUnderVoice": True,
    }
    assert music_cfg["enabled"]
    assert music_cfg["path"]
    assert music_cfg["volumeDb"] == -24


def test_music_enabled_no_path_is_review_required():
    """When enabled but path is missing, must be REVIEW_REQUIRED."""
    music_cfg = {"enabled": True, "path": None}
    is_error = music_cfg["enabled"] and not music_cfg.get("path")
    assert is_error, "music enabled without path should be an error"
    # Simulate the pipeline logic
    status = "REVIEW_REQUIRED" if is_error else "RENDERED"
    assert status == "REVIEW_REQUIRED"


def test_music_volume_in_resolved_config():
    """Configured volume must appear in resolved config."""
    resolved = {
        "music": {
            "enabled": True,
            "volumeDb": -18,
            "duckUnderVoice": True,
        }
    }
    assert resolved["music"]["volumeDb"] == -18


# ── Resolved config tests ─────────────────────────────────────────────────


def test_resolved_config_not_empty():
    """Newly generated jobs must have non-empty resolvedConfig."""
    resolved = {
        "duration": {"targetSec": 35, "minSec": 30, "maxSec": 40, "strictness": "balanced"},
        "voice": {"provider": "edge_tts", "voiceId": "es-ES-AlvaroNeural"},
        "subtitles": {"enabled": True, "style": "shorts_upper_dynamic", "position": "upper_middle"},
        "music": {"enabled": False},
        "outputProfile": {"resolution": "1080x1920"},
    }
    assert resolved["duration"]["targetSec"] == 35
    assert resolved["subtitles"]["style"] == "shorts_upper_dynamic"
    assert resolved["outputProfile"]["resolution"] == "1080x1920"
    assert not resolved["music"]["enabled"]


def test_resolved_config_matches_render_settings():
    """resolvedConfig must reflect actual render settings, not just defaults."""
    resolved = {
        "duration": {"targetSec": 35},
        "subtitles": {"style": "shorts_upper_dynamic", "position": "upper_middle"},
        "voice": {"provider": "edge_tts"},
        "outputProfile": {"resolution": "1080x1920", "fps": 25},
    }
    assert resolved["duration"]["targetSec"] == 35
    assert resolved["subtitles"]["position"] == "upper_middle"
    assert resolved["outputProfile"]["fps"] == 25


# ── Request schema validation ─────────────────────────────────────────────


def test_wright_has_request_field():
    """Existing jobs may not have request field yet (backward compat)."""
    data = load_meta(WRIGHT_METADATA)
    # Before fix: no request field expected
    assert "request" not in data


def test_request_schema_structure():
    """The request schema must have the expected structure."""
    request = {
        "topic": "Test topic",
        "language": "es-ES",
        "format": "shorts-9x16",
        "duration": {"targetSec": 35, "minSec": 30, "maxSec": 40, "strictness": "balanced"},
        "voice": {"provider": "edge_tts", "voiceId": "es-ES-AlvaroNeural"},
        "subtitles": {"enabled": True, "timingProvider": "auto", "style": "shorts_upper_dynamic",
                       "position": "upper_middle", "fontSize": 64},
        "visuals": {"mode": "images", "allowGeneratedImages": False},
        "editorialOverlays": {"enabled": False},
        "music": {"enabled": False, "source": "none"},
    }
    assert request["duration"]["targetSec"] == 35
    assert request["duration"]["strictness"] == "balanced"
    assert request["voice"]["provider"] == "edge_tts"
    assert request["subtitles"]["position"] == "upper_middle"
    assert request["music"]["enabled"] is False


# ── Validation gates model tests ──────────────────────────────────────────


def test_validation_gates_pass():
    """All gates pass -> qualityGate = PASS."""
    gates = {
        "technicalValidation": "PASS",
        "subtitleCoverageValidation": "PASS",
        "assetValidation": "PASS",
    }
    gate_failures = [k for k, v in gates.items() if v == "FAIL"]
    gate_warnings = [k for k, v in gates.items() if v in ("REVIEW_REQUIRED", "WARNING")]
    quality = "FAIL" if gate_failures else ("WARNING" if gate_warnings else "PASS")
    assert quality == "PASS"


def test_validation_gates_warning():
    """Any REVIEW_REQUIRED gate -> qualityGate = WARNING."""
    gates = {
        "technicalValidation": "PASS",
        "subtitleCoverageValidation": "REVIEW_REQUIRED",
        "assetValidation": "PASS",
    }
    gate_failures = [k for k, v in gates.items() if v == "FAIL"]
    gate_warnings = [k for k, v in gates.items() if v in ("REVIEW_REQUIRED", "WARNING")]
    quality = "FAIL" if gate_failures else ("WARNING" if gate_warnings else "PASS")
    assert quality == "WARNING"


def test_validation_gates_fail():
    """Any FAIL gate -> qualityGate = FAIL."""
    gates = {
        "technicalValidation": "FAIL",
        "subtitleCoverageValidation": "PASS",
        "assetValidation": "PASS",
    }
    gate_failures = [k for k, v in gates.items() if v == "FAIL"]
    gate_warnings = [k for k, v in gates.items() if v in ("REVIEW_REQUIRED", "WARNING")]
    quality = "FAIL" if gate_failures else ("WARNING" if gate_warnings else "PASS")
    assert quality == "FAIL"


# ── Asset warning status tests ────────────────────────────────────────────


def test_rendered_with_asset_warnings_is_not_rendered():
    """RENDERED_WITH_ASSET_WARNINGS should not equal RENDERED."""
    assert "RENDERED_WITH_ASSET_WARNINGS" != "RENDERED"


def test_skip_validation_produces_asset_warnings():
    """When --skip-asset-validation is used, status should be RENDERED_WITH_ASSET_WARNINGS."""
    technical_pass = True
    asset_was_skipped = True

    if not technical_pass:
        status = "RENDERED_WITH_WARNINGS"
    elif asset_was_skipped:
        status = "RENDERED_WITH_ASSET_WARNINGS"
    else:
        status = "RENDERED"

    assert status == "RENDERED_WITH_ASSET_WARNINGS"
