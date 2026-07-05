"""Regression tests for subtitle timing edge cases.

Fixtures:
- sentence_boundary_crossing: no words leak across sentence boundaries
- punctuation_restoration: trailing commas/periods recovered from canonical text
- no_cross_scene_leakage: cues respect scene window boundaries
- no_single_word_by_boundary: no single-word cue created solely by boundary handling

Run: python3 -m pytest tests/test_timing_regression.py -v
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
VENV_PYTHON = str(PROJECT / ".venv" / "bin" / "python3")
GENERATE_AUDIO = str(PROJECT / "bin" / "generate_audio.py")
PREPARE_JOB = str(PROJECT / "bin" / "prepare_job.py")

TEST_JOB_DIR = PROJECT / "data/videos/test-timing-regression"
REF_JOB_DIR = PROJECT / "data/videos/la-2026-07-01-173458"

SENTENCE_BOUNDARY_TEXT = (
    "Primera oración. Segunda oración. Tercera oración."
)

CROSS_SCENE_TEXT = (
    "Escena uno termina aquí. "
    "Escena dos comienza aquí."
)


def _build_metadata() -> dict:
    return {
        "jobId": "test-timing-regression",
        "status": "SCRIPT_DRAFT",
        "topic": "Regression tests for timing edge cases",
        "language": "es-ES",
        "format": "shorts-9x16",
        "targetDurationSeconds": 14,
        "script": {
            "title": "Timing Regression Test",
            "scenes": [
                {
                    "sceneNumber": 1,
                    "voiceover": SENTENCE_BOUNDARY_TEXT,
                    "subtitle": SENTENCE_BOUNDARY_TEXT,
                    "targetDurationSec": 7,
                    "visualPlan": {
                        "strategy": "historical_archive",
                        "editorialRole": "context_map",
                        "primaryAssetType": "historical_map",
                        "period": "Imperio Bizantino, 1453",
                        "location": "Constantinopla",
                        "preferredSources": ["wikimedia_commons"],
                        "allowGeneratedImage": False,
                    },
                    "narrativeBeats": [
                        {"beatIndex": 1, "text": SENTENCE_BOUNDARY_TEXT,
                         "visualIntent": "context_map", "startCueIndex": 0, "endCueIndex": 2}
                    ],
                },
                {
                    "sceneNumber": 2,
                    "voiceover": CROSS_SCENE_TEXT,
                    "subtitle": CROSS_SCENE_TEXT,
                    "targetDurationSec": 7,
                    "visualPlan": {
                        "strategy": "historical_archive",
                        "editorialRole": "battle_or_assault",
                        "primaryAssetType": "historical_art_or_document",
                        "period": "Imperio Otomano, 1453",
                        "location": "Constantinopla",
                        "preferredSources": ["wikimedia_commons"],
                        "allowGeneratedImage": False,
                    },
                    "narrativeBeats": [
                        {"beatIndex": 1, "text": CROSS_SCENE_TEXT,
                         "visualIntent": "battle_action", "startCueIndex": 0, "endCueIndex": 1}
                    ],
                },
            ],
        },
        "assets": [
            {
                "sceneNumber": sn,
                "selected": True,
                "path": str(REF_JOB_DIR / f"scenes/scene-0{sn}-01.jpg"),
                "strategy": "historical_archive",
                "assetType": "historical_map" if sn == 1 else "historical_art_or_document",
                "segments": [{
                    "segmentIndex": 1,
                    "path": str(REF_JOB_DIR / f"scenes/scene-0{sn}-01.jpg"),
                    "assetType": "historical_map" if sn == 1 else "historical_art_or_document",
                    "durationSec": 7.0,
                    "provider": "wikimedia_commons",
                    "sourceUrl": "https://example.com/img.jpg",
                    "license": "Public domain",
                    "score": 30,
                    "width": 828,
                    "height": 546,
                    "editorialRole": "context_map" if sn == 1 else "battle_or_assault",
                    "motionType": "static",
                    "transition": "cut",
                }],
            }
            for sn in (1, 2)
        ],
    }


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def _run_audio_and_load(metadata_path: Path) -> dict:
    """Run generate_audio.py then load metadata (tolerates REVIEW_REQUIRED exit code)."""
    r = subprocess.run(
        [VENV_PYTHON, GENERATE_AUDIO, str(metadata_path),
         "--continuous", "--voice", "es-ES-AlvaroNeural",
         "--subtitle-timing-provider", "edge_tts"],
        capture_output=True, text=True, timeout=120
    )
    meta = json.loads(metadata_path.read_text())
    cues_found = any(
        sc.get("subtitleTiming", {}).get("cues", [])
        for sc in meta.get("script", {}).get("scenes", [])
    )
    assert cues_found, f"generate_audio produced no cues: stdout={r.stdout[:500]}"
    return meta


def setup_job() -> dict:
    TEST_JOB_DIR.mkdir(parents=True, exist_ok=True)
    scenes_dir = TEST_JOB_DIR / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    meta = _build_metadata()
    meta_path = TEST_JOB_DIR / "metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    for asset in meta["assets"]:
        src = Path(asset["path"])
        if src.exists():
            dst = scenes_dir / src.name
            if not dst.exists():
                dst.write_bytes(src.read_bytes())
    return json.loads(meta_path.read_text())


def test_sentence_boundary_crossing():
    """No words leak across sentence boundaries within the same scene."""
    setup_job()
    meta = _run_audio_and_load(TEST_JOB_DIR / "metadata.json")
    scene1_cues = meta["script"]["scenes"][0].get("subtitleTiming", {}).get("cues", [])
    all_cue_text = " ".join(c["text"] for c in scene1_cues)
    assert "oración" in all_cue_text
    cues_text = " | ".join(c["text"] for c in scene1_cues)
    assert "Segunda" not in scene1_cues[0]["text"], \
        f"First cue leaks into second sentence: {cues_text}"
    assert "Tercera" not in scene1_cues[0]["text"], \
        f"First cue leaks into third sentence: {cues_text}"


def test_punctuation_restoration():
    """Trailing punctuation recovered from canonical text in Edge mode."""
    setup_job()
    meta = _run_audio_and_load(TEST_JOB_DIR / "metadata.json")
    scene1_cues = meta["script"]["scenes"][0].get("subtitleTiming", {}).get("cues", [])
    has_period = any("oración." in c["text"] for c in scene1_cues)
    assert has_period, \
        f"No cue contains period: {[c['text'] for c in scene1_cues]}"


def test_no_cross_scene_leakage():
    """Cues from scene 1 do not leak into scene 2 window and vice versa.
    Uses unique words from each scene to avoid false positives."""
    setup_job()
    meta = _run_audio_and_load(TEST_JOB_DIR / "metadata.json")
    scene1_cues = meta["script"]["scenes"][0].get("subtitleTiming", {}).get("cues", [])
    scene2_cues = meta["script"]["scenes"][1].get("subtitleTiming", {}).get("cues", [])
    # Scene 1 has "Primera oración" — should not appear in scene 2 cues
    scene1_unique = "Primera"
    # Scene 2 has "comienza aquí" — should not appear in scene 1 cues
    scene2_unique = "comienza"
    for cue in scene1_cues:
        assert scene2_unique not in cue["text"], \
            f"Scene 1 cue contains scene 2 text: {cue['text']}"
    for cue in scene2_cues:
        assert scene1_unique not in cue["text"], \
            f"Scene 2 cue contains scene 1 text: {cue['text']}"


def test_no_single_word_by_boundary():
    """No single-word cue is created solely by sentence-boundary handling
    (a single-word cue is allowed if it's a brief word like an
    interjection, or is the last cue at a scene boundary)."""
    setup_job()
    meta = _run_audio_and_load(TEST_JOB_DIR / "metadata.json")
    scene1_cues = meta["script"]["scenes"][0].get("subtitleTiming", {}).get("cues", [])
    scene1_end = scene1_cues[-1]["endSec"] if scene1_cues else 999
    for cue in scene1_cues:
        word_count = len(cue["text"].split())
        is_last_cue = cue["endSec"] >= scene1_end - 0.1
        if word_count < 2 and is_last_cue:
            continue  # Allow single-word cue at scene boundary
        assert word_count >= 2, \
            f"Single-word cue found: '{cue['text']}' (start={cue['startSec']})"
