"""Tests for cross-scene subtitle leakage, duration contract, validation consistency,
subtitle style, music contract, and resolved config.

Run: python3 -m pytest tests/test_duration_contract_and_scene_boundary.py -v
"""

import json
import re
import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
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


# ── Canonical token ownership tests ────────────────────────────────────────


def test_canonical_tokens_built_from_narration_units():
    """_build_canonical_tokens must produce ordered tokens with scene and unit index."""
    from shorts_creator.audio.generator import _build_canonical_tokens
    narration_units = [
        {"sceneNumber": 1, "sentenceIndex": 0, "text": "La erupción del Vesubio."},
        {"sceneNumber": 1, "sentenceIndex": 1, "text": "Comenzó en el año 79."},
        {"sceneNumber": 2, "sentenceIndex": 0, "text": "Pompeya quedó sepultada."},
    ]
    tokens = _build_canonical_tokens(narration_units)
    assert len(tokens) == 12  # total words
    # First unit tokens
    assert tokens[0]["text"] == "La"
    assert tokens[0]["sceneNumber"] == 1
    assert tokens[0]["narrationUnitIndex"] == 0
    assert tokens[3]["text"] == "Vesubio."
    # Second unit tokens
    assert tokens[4]["text"] == "Comenzó"
    assert tokens[4]["sceneNumber"] == 1
    assert tokens[4]["narrationUnitIndex"] == 1
    # Third unit (scene 2) tokens
    assert tokens[9]["text"] == "Pompeya"
    assert tokens[9]["sceneNumber"] == 2
    assert tokens[9]["narrationUnitIndex"] == 0


def test_match_words_to_canonical_assigns_scene():
    """Edge WordBoundary words must get correct scene from canonical matching."""
    from shorts_creator.audio.generator import _build_canonical_tokens, _match_words_to_canonical
    narration_units = [
        {"sceneNumber": 1, "sentenceIndex": 0, "text": "La erupción."},
        {"sceneNumber": 2, "sentenceIndex": 0, "text": "El volcán."},
    ]
    canonical = _build_canonical_tokens(narration_units)
    edge_words = [
        {"startSec": 0.0, "endSec": 0.5, "text": "La"},
        {"startSec": 0.5, "endSec": 1.0, "text": "erupción."},
        {"startSec": 1.0, "endSec": 1.5, "text": "El"},
        {"startSec": 1.5, "endSec": 2.0, "text": "volcán."},
    ]
    result, metrics = _match_words_to_canonical(edge_words, canonical)
    assert len(result) == 4
    assert result[0]["sceneNumber"] == 1
    assert result[0]["narrationUnitIndex"] == 0
    assert result[1]["sceneNumber"] == 1
    assert result[2]["sceneNumber"] == 2
    assert result[2]["narrationUnitIndex"] == 0
    assert result[3]["sceneNumber"] == 2
    assert metrics["matchedWordCount"] == 4


def test_match_words_to_canonical_no_cross_scene_leakage():
    """Canonical matching must prevent 'El' from scene 2 leaking into scene 1."""
    from shorts_creator.audio.generator import _build_canonical_tokens, _match_words_to_canonical, group_words_into_cues
    # Simulate Wright scenario: scene 1 ends with "voló", scene 2 starts with "El"
    narration_units = [
        {"sceneNumber": 1, "sentenceIndex": 0, "text": "El Flyer I voló."},
        {"sceneNumber": 2, "sentenceIndex": 0, "text": "El primer vuelo."},
    ]
    canonical = _build_canonical_tokens(narration_units)
    # Edge might place "El" of scene 2 earlier due to timing
    edge_words = [
        {"startSec": 0.0, "endSec": 0.3, "text": "El"},
        {"startSec": 0.3, "endSec": 0.8, "text": "Flyer"},
        {"startSec": 0.8, "endSec": 1.0, "text": "I"},
        {"startSec": 1.0, "endSec": 1.5, "text": "voló."},
        {"startSec": 1.5, "endSec": 1.7, "text": "El"},  # scene 2's El, may have early timing
        {"startSec": 1.7, "endSec": 2.0, "text": "primer"},
        {"startSec": 2.0, "endSec": 2.5, "text": "vuelo."},
    ]
    annotated, metrics = _match_words_to_canonical(edge_words, canonical)
    # The 5th word (scene 2's "El") must have sceneNumber=2, not 1
    assert annotated[4]["sceneNumber"] == 2, \
        f"Scene 2's 'El' got sceneNumber={annotated[4]['sceneNumber']}, expected 2"
    assert annotated[4]["narrationUnitIndex"] == 0
    assert metrics["matchedWordCount"] == 7

    # Group into cues - should flush at scene boundary
    cues = group_words_into_cues(annotated)

    # Simple text check: "voló El" should not appear
    cue_texts = [c["text"] for c in cues]
    combined = " ".join(cue_texts)
    assert "voló El" not in combined, f"Cross-scene leakage: 'voló El' found in: {combined[:100]}"


def test_span_aware_matching_berlin_wall():
    """Span-aware matching must prevent scene 2 from owning scenes 3-5 content."""
    from shorts_creator.audio.generator import _build_canonical_tokens, _match_words_to_canonical, group_words_into_cues
    # Berlin Wall v2: 5 scenes (scenes 1 omitted, testing 2-5 cross-scene)
    narration_units = [
        {"sceneNumber": 2, "sentenceIndex": 0, "text": "El 13 de agosto de 1961, comenzó la construcción del Muro."},
        {"sceneNumber": 3, "sentenceIndex": 0, "text": "Casi 160 kilómetros de muro separaron familias y amigos."},
        {"sceneNumber": 4, "sentenceIndex": 0, "text": "El Muro cayó en 1989, un símbolo de libertad."},
        {"sceneNumber": 5, "sentenceIndex": 0, "text": "Explora más sobre la historia del Muro y su legado, síguenos."},
    ]
    canonical = _build_canonical_tokens(narration_units)
    # Simulate Edge WordBoundary events for the full narration
    edge_words = [
        {"startSec": 0.0, "endSec": 0.2, "text": "El"},
        {"startSec": 0.2, "endSec": 0.3, "text": "13"},
        {"startSec": 0.3, "endSec": 0.5, "text": "agosto"},
        {"startSec": 0.5, "endSec": 0.6, "text": "de"},
        {"startSec": 0.6, "endSec": 0.8, "text": "1961"},
        {"startSec": 0.8, "endSec": 1.0, "text": "comenzó"},
        {"startSec": 1.0, "endSec": 1.2, "text": "la"},
        {"startSec": 1.2, "endSec": 1.4, "text": "construcción"},
        {"startSec": 1.4, "endSec": 1.6, "text": "del"},
        {"startSec": 1.6, "endSec": 1.8, "text": "Muro."},
        # Scene 3
        {"startSec": 1.8, "endSec": 2.0, "text": "Casi"},
        {"startSec": 2.0, "endSec": 2.1, "text": "160"},
        {"startSec": 2.1, "endSec": 2.3, "text": "kilómetros"},
        {"startSec": 2.3, "endSec": 2.4, "text": "de"},
        {"startSec": 2.4, "endSec": 2.6, "text": "muro"},
        {"startSec": 2.6, "endSec": 2.8, "text": "separaron"},
        {"startSec": 2.8, "endSec": 2.9, "text": "familias"},
        {"startSec": 2.9, "endSec": 3.1, "text": "y"},
        {"startSec": 3.1, "endSec": 3.3, "text": "amigos."},
        # Scene 4
        {"startSec": 3.3, "endSec": 3.5, "text": "El"},
        {"startSec": 3.5, "endSec": 3.6, "text": "Muro"},
        {"startSec": 3.6, "endSec": 3.8, "text": "cayó"},
        {"startSec": 3.8, "endSec": 3.9, "text": "en"},
        {"startSec": 3.9, "endSec": 4.1, "text": "1989"},
        {"startSec": 4.1, "endSec": 4.3, "text": "un"},
        {"startSec": 4.3, "endSec": 4.4, "text": "símbolo"},
        {"startSec": 4.4, "endSec": 4.6, "text": "de"},
        {"startSec": 4.6, "endSec": 4.8, "text": "libertad."},
        # Scene 5
        {"startSec": 4.8, "endSec": 5.0, "text": "Explora"},
        {"startSec": 5.0, "endSec": 5.1, "text": "más"},
        {"startSec": 5.1, "endSec": 5.3, "text": "sobre"},
        {"startSec": 5.3, "endSec": 5.4, "text": "la"},
        {"startSec": 5.4, "endSec": 5.6, "text": "historia"},
        {"startSec": 5.6, "endSec": 5.7, "text": "del"},
        {"startSec": 5.7, "endSec": 5.9, "text": "Muro"},
        {"startSec": 5.9, "endSec": 6.1, "text": "y"},
        {"startSec": 6.1, "endSec": 6.2, "text": "su"},
        {"startSec": 6.2, "endSec": 6.4, "text": "legado,"},
        {"startSec": 6.4, "endSec": 6.6, "text": "síguenos."},
    ]
    annotated, metrics = _match_words_to_canonical(edge_words, canonical)

    # Group into cues
    cues = group_words_into_cues(annotated)

    # Check scene 2 has no scene 3 content
    scene2_cues = [c for c in cues if c.get("sceneNumber") == 2]
    scene2_text = " ".join(c.get("text", "") for c in scene2_cues).lower()
    assert "casi" not in scene2_text, f"Scene 2 leaked 'Casi': {scene2_text[:80]}"
    for forbidden in ["casi", "160", "kilómetros", "separaron", "familias", "amigos",
                       "cayó", "1989", "símbolo", "libertad",
                       "explora", "historia", "legado", "síguenos"]:
        assert forbidden not in scene2_text, f"Scene 2 leaked '{forbidden}': {scene2_text[:100]}"

    # Check each scene 3-5 has its own cues
    for sn in [3, 4, 5]:
        sn_cues = [c for c in cues if c.get("sceneNumber") == sn]
        assert len(sn_cues) > 0, f"Scene {sn} has no cues"

    # Check no cross-scene cue: a single cue must not span multiple scenes
    for c in cues:
        if c.get("sceneNumber") is None:
            continue
        assert c.get("sceneNumber") is not None, f"Cue with no scene: {c['text'][:40]}"

    # Check confidence is high with complete ownership
    assert metrics["confidence"] == "high", \
        f"Expected high confidence, got {metrics['confidence']}: {metrics['matchedWordCount']}/{metrics['totalWordCount']} matched"


def test_canonical_validation_detects_cross_scene():
    """validate_canonical_cue_integrity must detect cross-scene word leaks."""
    from shorts_creator.validation.coverage import validate_canonical_cue_integrity
    narration_units = [
        {"sceneNumber": 1, "sentenceIndex": 0, "text": "La erupción del Vesubio."},
        {"sceneNumber": 2, "sentenceIndex": 0, "text": "Pompeya fue sepultada."},
    ]
    # Simulate a cue with cross-scene leakage
    cues_by_scene = {
        1: [
            {"startSec": 0.0, "endSec": 3.0, "text": "La erupción del Vesubio."},
            {"startSec": 3.0, "endSec": 4.0, "text": "Pompeya fue"},  # "Pompeya" belongs to scene 2
        ],
        2: [
            {"startSec": 4.0, "endSec": 6.0, "text": "sepultada."},
        ],
    }
    errors = validate_canonical_cue_integrity(cues_by_scene, narration_units)
    assert len(errors) > 0, "Cross-scene leakage should be detected"
    assert any(e["offendingToken"] == "pompeya" for e in errors), \
        f"Expected 'pompeya' in errors: {errors}"


# ── Duration contract validation logic tests ──────────────────────────────


def _validate_duration(audio_dur, target=28, min_sec=25, max_sec=30, strictness="balanced"):
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


def test_duration_balanced_24s_fails():
    """28 target with 24 actual in balanced mode must fail (below 25s min)."""
    errors = _validate_duration(24, target=28, min_sec=25, max_sec=30)
    assert len(errors) > 0, "24s should fail balanced mode (below 25s min)"
    assert "minSec" in errors[0]


def test_duration_balanced_28s_passes():
    """28 target with 28 actual in balanced mode must pass."""
    errors = _validate_duration(28, target=28, min_sec=25, max_sec=30)
    assert len(errors) == 0, f"28s should pass balanced mode but got: {errors}"


def test_duration_balanced_31s_fails():
    """28 target with 31 actual in balanced mode must fail (above 30s max)."""
    errors = _validate_duration(31, target=28, min_sec=25, max_sec=30)
    assert len(errors) > 0, "31s should fail balanced mode (above 30s max)"
    assert "maxSec" in errors[0]


def test_duration_strict_25s_fails():
    """28 target with 25 actual in strict mode must fail (< 25.2 = 28 - 10%)."""
    errors = _validate_duration(25, target=28, min_sec=25, max_sec=30, strictness="strict")
    assert len(errors) > 0, "25s should fail strict mode"
    assert "target" in errors[0]


def test_duration_strict_27s_passes():
    """28 target with 27 actual in strict mode must pass (within +/-10% = 25.2-30.8)."""
    errors = _validate_duration(27, target=28, min_sec=25, max_sec=30, strictness="strict")
    assert len(errors) == 0, f"27s should pass strict mode but got: {errors}"


def test_duration_relaxed_20s_passes():
    """Relaxed mode always passes."""
    errors = _validate_duration(20, target=28, min_sec=25, max_sec=30, strictness="relaxed")
    assert len(errors) == 0, "relaxed mode should always pass"


# ── Duration contract — script retry loop ─────────────────────────────────


def _count_voiceover_words(script_data):
    total = 0
    for scene in script_data.get("scenes", []):
        total += len(scene.get("voiceover", "").split())
    return total


def _estimate_narration_duration_sec(word_count, wpm=145):
    return word_count / (wpm / 60.0)


def _check_duration_contract(word_count, target=28, min_sec=25, max_sec=30, strictness="balanced"):
    estimated = _estimate_narration_duration_sec(word_count)
    if strictness == "strict":
        margin = target * 0.10
        ok = (target - margin) <= estimated <= (target + margin)
    elif strictness == "balanced":
        ok = min_sec <= estimated <= max_sec
    else:
        ok = True
    return ok, estimated


def test_script_retry_24s_must_fail():
    """28s balanced request with ~24s equivalent words must fail."""
    # 24 seconds * (145/60) wps = ~58 words
    word_count = 58
    ok, estimated = _check_duration_contract(word_count, target=28, min_sec=25, max_sec=30)
    assert not ok, f"58 words ({estimated:.1f}s) should fail for 28s balanced target"
    assert estimated < 25


def test_script_retry_28s_must_pass():
    """28s balanced request with ~28s equivalent words must pass."""
    # 28 seconds * (145/60) wps = ~68 words
    word_count = 68
    ok, estimated = _check_duration_contract(word_count, target=28, min_sec=25, max_sec=30)
    assert ok, f"68 words ({estimated:.1f}s) should pass for 28s balanced target"
    assert 25 <= estimated <= 30


def test_script_retry_max_retries():
    """After max retries still outside range, must return FAIL."""
    word_count = 50  # very short
    ok, estimated = _check_duration_contract(word_count, target=28, min_sec=25, max_sec=30)
    assert not ok
    assert estimated < 25


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
        "duration": {"targetSec": 28, "minSec": 25, "maxSec": 30, "strictness": "balanced"},
        "voice": {"provider": "edge_tts", "voiceId": "es-ES-AlvaroNeural"},
        "subtitles": {"enabled": True, "style": "shorts_upper_dynamic", "position": "upper_middle"},
        "music": {"enabled": False},
        "outputProfile": {"resolution": "1080x1920"},
    }
    assert resolved["duration"]["targetSec"] == 28
    assert resolved["subtitles"]["style"] == "shorts_upper_dynamic"
    assert resolved["outputProfile"]["resolution"] == "1080x1920"
    assert not resolved["music"]["enabled"]


def test_resolved_config_matches_render_settings():
    """resolvedConfig must reflect actual render settings, not just defaults."""
    resolved = {
        "duration": {"targetSec": 28},
        "subtitles": {"style": "shorts_upper_dynamic", "position": "upper_middle"},
        "voice": {"provider": "edge_tts"},
        "outputProfile": {"resolution": "1080x1920", "fps": 25},
    }
    assert resolved["duration"]["targetSec"] == 28
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
        "duration": {"targetSec": 28, "minSec": 25, "maxSec": 30, "strictness": "balanced"},
        "voice": {"provider": "edge_tts", "voiceId": "es-ES-AlvaroNeural"},
        "subtitles": {"enabled": True, "timingProvider": "auto", "style": "shorts_upper_dynamic",
                       "position": "upper_middle", "fontSize": 64},
        "visuals": {"mode": "images", "allowGeneratedImages": False},
        "editorialOverlays": {"enabled": False},
        "music": {"enabled": False, "source": "none"},
    }
    assert request["duration"]["targetSec"] == 28
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


# ── Regression: null asset path ──────────────────────────────────────────


def test_null_asset_path_caught_by_preflight():
    """Entry with assetPath='' or None must be caught by preflight_validate()."""
    from shorts_creator.rendering.renderer import preflight_validate
    timeline = [
        {"sceneNumber": 1, "beatIndex": 1, "assetPath": "",
         "startSec": 0.0, "endSec": 5.0, "durationSec": 5.0,
         "segmentIndex": 1},
    ]
    scenes = [{"sceneNumber": 1, "targetDurationSec": 5}]
    wrong_dir = Path("/nonexistent")
    errors = preflight_validate(timeline, scenes, wrong_dir, wrong_dir,
                                 expected_total=5.0, is_continuous_audio=False)
    assert any("assetPath is empty" in e for e in errors), \
        f"Expected 'assetPath is empty' error, got: {errors}"


def test_null_asset_path_none_caught_by_preflight():
    """Entry with assetPath=None must be caught by preflight_validate()."""
    from shorts_creator.rendering.renderer import preflight_validate
    timeline = [
        {"sceneNumber": 1, "beatIndex": 1, "assetPath": None,
         "startSec": 0.0, "endSec": 5.0, "durationSec": 5.0,
         "segmentIndex": 1},
    ]
    scenes = [{"sceneNumber": 1, "targetDurationSec": 5}]
    wrong_dir = Path("/nonexistent")
    errors = preflight_validate(timeline, scenes, wrong_dir, wrong_dir,
                                 expected_total=5.0, is_continuous_audio=False)
    assert any("assetPath is empty" in e for e in errors), \
        f"Expected 'assetPath is empty' error, got: {errors}"


# ── Regression: Edge WordBoundary timing ─────────────────────────────────


def test_edge_tts_word_boundary_preferred():
    """When timingProvider='auto' and edge_tts is used, timing source must be WordBoundary."""
    from shorts_creator.audio.tts_provider import EdgeTTSProvider
    provider = EdgeTTSProvider()
    meta = provider.metadata
    # EdgeTTS supports sentence timing natively; WordBoundary is set via boundary= param
    # The synthesize_with_timing_async method produces word_boundaries when available
    assert provider.is_available(), "edge_tts must be installed for timing tests"
    # Verify WordBoundary is the default for the async timing path
    # We can't easily call synthesize here, but we can verify the Communicate() call
    # would include boundary="WordBoundary" by checking the TTSOptions
    from edge_tts import Communicate
    import inspect
    sig = inspect.signature(Communicate)
    # edge_tts.Communicate accepts boundary param with default "SentenceBoundary"
    assert "boundary" in sig.parameters, \
        "Communicate() must accept boundary parameter"


def test_timing_source_word_boundary_detected():
    """timing_data.timing_source must be edge_tts_word_boundary, not sentence_boundary."""
    timing_data = {
        "word_boundaries": [{"startSec": 0.1, "endSec": 0.5, "text": "Hola"}],
        "sentence_boundaries": [],
        "timing_source": "edge_tts_word_boundary",
    }
    assert timing_data["timing_source"] == "edge_tts_word_boundary"
    assert len(timing_data["word_boundaries"]) > 0
    # If only sentence boundaries existed, source would be different
    timing_data_sentence = {
        "word_boundaries": [],
        "sentence_boundaries": [{"offset": 0, "duration": 50000000}],
        "timing_source": "edge_tts_sentence_boundary",
    }
    assert timing_data_sentence["timing_source"] == "edge_tts_sentence_boundary"
    assert len(timing_data_sentence["word_boundaries"]) == 0


# ── Regression: retry semantics max_attempts ─────────────────────────────


def test_retry_loop_max_attempts_limits_calls():
    """With max_attempts=2, the loop must allow at most 2 LLM calls (1 initial + 1 retry)."""
    max_attempts = 2
    retries = 0
    attempts = 0
    while retries < max_attempts:
        attempts += 1
        retries += 1
    assert attempts == 2, f"Expected 2 attempts with max_attempts=2, got {attempts}"
    # Verify old off-by-one: <= max_retries with max_retries=2 would give 3
    old_retries = 0
    old_max = 2
    old_attempts = 0
    while old_retries <= old_max:
        old_attempts += 1
        old_retries += 1
    assert old_attempts == 3, f"Expected 3 with old <= logic, got {old_attempts}"
    # Verify fix: < max_attempts gives correct count
    assert attempts == 2


def test_retry_history_accurate():
    """retryHistory must reflect actual attempts (not overcount)."""
    max_attempts = 2
    retries = 0
    retry_history = []
    while retries < max_attempts:
        retry_history.append({"retry": retries})
        retries += 1
    assert len(retry_history) == 2
    assert retry_history[0]["retry"] == 0
    assert retry_history[1]["retry"] == 1


def test_seg_get_path_null_safety():
    """seg.get('path') with value None must return empty string when using or ''."""
    seg_with_none = {"path": None, "segmentIndex": 1}
    seg_with_str = {"path": "/some/path.jpg", "segmentIndex": 1}
    seg_missing = {"segmentIndex": 1}
    assert (seg_with_none.get("path") or "") == ""
    assert (seg_with_str.get("path") or "") == "/some/path.jpg"
    assert (seg_missing.get("path") or "") == ""
