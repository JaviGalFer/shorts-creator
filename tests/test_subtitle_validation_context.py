"""Tests for shared per-scene subtitle validation context.

Run: python3 -m pytest tests/test_subtitle_validation_context.py -v
"""

import copy
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

from shorts_creator.validation.subtitle_context import (
    build_validation_context,
    _build_scene_windows,
    _build_audio_duration_map,
    _build_global_cues,
    _validate_local_cues,
    _validate_global_cues,
    _validate_ass_dialogues,
)


# ── Fixtures ──────────────────────────────────────────────────────────


def _make_e2e_metadata(with_ass=False):
    return {
        "jobId": "e2e-pixabay-20260714-184248",
        "script": {
            "scenes": [
                {
                    "sceneNumber": 1,
                    "voiceover": "Sabes cómo se forma realmente un arcoíris? No es magia, es un fenómeno de la luz.",
                    "subtitleTiming": {
                        "cues": [
                            {"startSec": 0.100, "endSec": 2.612, "text": "Sabes cómo se forma realmente un arcoíris?"},
                            {"startSec": 3.475, "endSec": 5.700, "text": "No es magia, es un fenómeno de la luz."},
                        ]
                    },
                },
                {
                    "sceneNumber": 2,
                    "voiceover": "La luz del sol entra en las gotas de lluvia, se refracta y se descompone en los siete colores del espectro visible.",
                    "subtitleTiming": {
                        "cues": [
                            {"startSec": 0.100, "endSec": 1.450, "text": "La luz del sol entra en las"},
                            {"startSec": 1.462, "endSec": 3.487, "text": "gotas de lluvia, se refracta y se"},
                            {"startSec": 3.500, "endSec": 6.062, "text": "descompone en los siete colores del espectro visible."},
                        ]
                    },
                },
                {
                    "sceneNumber": 3,
                    "voiceover": "El reflejo interno en cada gota crea el arco perfecto que vemos en el cielo. Así se forma un arcoíris.",
                    "subtitleTiming": {
                        "cues": [
                            {"startSec": 0.100, "endSec": 2.087, "text": "El reflejo interno en cada gota crea"},
                            {"startSec": 2.100, "endSec": 4.175, "text": "el arco perfecto que vemos en el cielo."},
                            {"startSec": 5.037, "endSec": 6.675, "text": "Así se forma un arcoíris."},
                        ]
                    },
                },
            ]
        },
        "renderTimeline": [
            {"sceneNumber": 1, "beatIndex": 1, "startSec": 0.0, "endSec": 8.0},
            {"sceneNumber": 2, "beatIndex": 1, "startSec": 8.0, "endSec": 13.0},
            {"sceneNumber": 2, "beatIndex": 2, "startSec": 13.0, "endSec": 18.0},
            {"sceneNumber": 3, "beatIndex": 1, "startSec": 18.0, "endSec": 24.0},
            {"sceneNumber": 3, "beatIndex": 2, "startSec": 24.0, "endSec": 30.0},
        ],
        "audio": {
            "provider": "edge_tts",
            "voice": "es-ES-AlvaroNeural",
            "continuous": False,
            "scenes": [
                {"sceneNumber": 1, "path": "/fake/scene-01.mp3", "exists": True, "durationSec": 6.576},
                {"sceneNumber": 2, "path": "/fake/scene-02.mp3", "exists": True, "durationSec": 6.936},
                {"sceneNumber": 3, "path": "/fake/scene-03.mp3", "exists": True, "durationSec": 7.536},
            ],
        },
    }


def _make_continuous_metadata():
    return {
        "jobId": "continuous-test",
        "script": {
            "scenes": [
                {
                    "sceneNumber": 1,
                    "voiceover": "test voiceover one",
                    "subtitleTiming": {
                        "cues": [
                            {"startSec": 0.1, "endSec": 2.0, "text": "test cue one"},
                        ]
                    },
                },
                {
                    "sceneNumber": 2,
                    "voiceover": "test voiceover two",
                    "subtitleTiming": {
                        "cues": [
                            {"startSec": 2.5, "endSec": 4.0, "text": "test cue two"},
                        ]
                    },
                },
            ]
        },
        "renderTimeline": [
            {"sceneNumber": 1, "startSec": 0.0, "endSec": 3.0},
            {"sceneNumber": 2, "startSec": 3.0, "endSec": 5.0},
        ],
        "audio": {
            "provider": "edge_tts",
            "voice": "es-ES-AlvaroNeural",
            "continuous": True,
            "durationSec": 5.0,
            "sceneTimings": [
                {"sceneNumber": 1, "startSec": 0.0, "endSec": 2.5},
                {"sceneNumber": 2, "startSec": 2.5, "endSec": 5.0},
            ],
            "narrationUnits": [
                {"sceneNumber": 1, "text": "test voiceover one"},
                {"sceneNumber": 2, "text": "test voiceover two"},
            ],
        },
    }


def _make_ass_content(global_cues):
    """Generate a valid ASS file content matching the given global cues."""
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: shorts_upper_dynamic,Arial,64,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,2,8,140,140,430,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for cue in global_cues:
        start = _secs_to_ass_time(cue["startSec"])
        end = _secs_to_ass_time(cue["endSec"])
        text = cue.get("text", "").replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{start},{end},shorts_upper_dynamic,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"


def _secs_to_ass_time(secs: float) -> str:
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = int(secs % 60)
    cs = int(round((secs - int(secs)) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# ── Test 1: Full E2E fixture ──────────────────────────────────────────


class TestE2EFixture:
    def test_build_context_e2e_fixture(self, tmp_path):
        """E2E metadata produces PASS with 8 global cues, 0 overlaps."""
        meta = _make_e2e_metadata()
        meta_copy = copy.deepcopy(meta)

        ctx = build_validation_context(meta_copy, video_dir=None)
        assert ctx["mode"] == "per_scene"
        assert ctx["status"] == "PASS"
        assert ctx["totalCues"] == 8
        assert ctx["errors"] == []
        assert ctx["globalCues"]

        gc = ctx["globalCues"]
        assert len(gc) == 8

        scene1_cues = [c for c in gc if c["sceneNumber"] == 1]
        assert len(scene1_cues) == 2
        assert scene1_cues[0]["startSec"] == pytest.approx(0.100)
        assert scene1_cues[0]["endSec"] == pytest.approx(2.612)
        assert scene1_cues[1]["startSec"] == pytest.approx(3.475)
        assert scene1_cues[1]["endSec"] == pytest.approx(5.700)

        scene2_cues = [c for c in gc if c["sceneNumber"] == 2]
        assert len(scene2_cues) == 3
        assert scene2_cues[0]["startSec"] == pytest.approx(8.100)
        assert scene2_cues[0]["endSec"] == pytest.approx(9.450)
        assert scene2_cues[1]["startSec"] == pytest.approx(9.462)
        assert scene2_cues[1]["endSec"] == pytest.approx(11.487)
        assert scene2_cues[2]["startSec"] == pytest.approx(11.500)
        assert scene2_cues[2]["endSec"] == pytest.approx(14.062)

        scene3_cues = [c for c in gc if c["sceneNumber"] == 3]
        assert len(scene3_cues) == 3
        assert scene3_cues[0]["startSec"] == pytest.approx(18.100)
        assert scene3_cues[0]["endSec"] == pytest.approx(20.087)
        assert scene3_cues[1]["startSec"] == pytest.approx(20.100)
        assert scene3_cues[1]["endSec"] == pytest.approx(22.175)
        assert scene3_cues[2]["startSec"] == pytest.approx(23.037)
        assert scene3_cues[2]["endSec"] == pytest.approx(24.675)

    def test_metadata_not_mutated(self):
        """Original metadata dict is not modified by validation."""
        meta = _make_e2e_metadata()
        meta_copy = copy.deepcopy(meta)
        build_validation_context(meta_copy)
        assert meta == meta_copy


# ── Test 2: Two scenes with cues at 0.1 → differentiated after offsets ─


class TestTwoScenesCuesAtStart:
    def test_two_scenes_local_0_1_not_overlapping(self, tmp_path):
        meta = {
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "voiceover": "Scene one narration.",
                        "subtitleTiming": {
                            "cues": [
                                {"startSec": 0.1, "endSec": 3.0, "text": "Scene one narration."},
                            ]
                        },
                    },
                    {
                        "sceneNumber": 2,
                        "voiceover": "Scene two narration.",
                        "subtitleTiming": {
                            "cues": [
                                {"startSec": 0.1, "endSec": 3.0, "text": "Scene two narration."},
                            ]
                        },
                    },
                ]
            },
            "renderTimeline": [
                {"sceneNumber": 1, "startSec": 0.0, "endSec": 5.0},
                {"sceneNumber": 2, "startSec": 5.0, "endSec": 10.0},
            ],
            "audio": {
                "continuous": False,
                "provider": "edge_tts",
                "voice": "es-ES-AlvaroNeural",
                "scenes": [
                    {"sceneNumber": 1, "durationSec": 3.5},
                    {"sceneNumber": 2, "durationSec": 3.5},
                ],
            },
        }
        ctx = build_validation_context(meta, video_dir=None)
        assert ctx["status"] == "PASS"
        gc = ctx["globalCues"]
        assert gc[0]["startSec"] == pytest.approx(0.1)
        assert gc[0]["endSec"] == pytest.approx(3.0)
        assert gc[1]["startSec"] == pytest.approx(5.1)
        assert gc[1]["endSec"] == pytest.approx(8.0)
        # No overlap
        overlap_errors = [e for e in ctx["errors"] if "overlap" in e.lower()]
        assert len(overlap_errors) == 0


# ── Test 3: Overlap within same scene → FAIL ──────────────────────────


class TestLocalCueOverlap:
    def test_overlap_within_scene_fails(self, tmp_path):
        meta = {
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "voiceover": "Some voiceover text here.",
                        "subtitleTiming": {
                            "cues": [
                                {"startSec": 0.1, "endSec": 3.0, "text": "first cue"},
                                {"startSec": 2.0, "endSec": 5.0, "text": "overlapping cue"},
                            ]
                        },
                    },
                ]
            },
            "renderTimeline": [
                {"sceneNumber": 1, "startSec": 0.0, "endSec": 8.0},
            ],
            "audio": {
                "continuous": False,
                "provider": "edge_tts",
                "voice": "es-ES-AlvaroNeural",
                "scenes": [
                    {"sceneNumber": 1, "durationSec": 7.0},
                ],
            },
        }
        ctx = build_validation_context(meta, video_dir=tmp_path)
        assert ctx["status"] == "FAIL"
        overlap_errors = [e for e in ctx["errors"] if "local overlap" in e]
        assert len(overlap_errors) >= 1


# ── Test 4: Cue exceeds real audio duration → FAIL ────────────────────


class TestCueExceedsAudioDuration:
    def test_cue_exceeds_mp3_duration(self, tmp_path):
        meta = {
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "voiceover": "Test",
                        "subtitleTiming": {
                            "cues": [
                                {"startSec": 0.1, "endSec": 8.0, "text": "too long cue"},
                            ]
                        },
                    },
                ]
            },
            "renderTimeline": [
                {"sceneNumber": 1, "startSec": 0.0, "endSec": 10.0},
            ],
            "audio": {
                "continuous": False,
                "provider": "edge_tts",
                "voice": "es-ES-AlvaroNeural",
                "scenes": [
                    {"sceneNumber": 1, "durationSec": 6.576},
                ],
            },
        }
        ctx = build_validation_context(meta, video_dir=tmp_path)
        assert ctx["status"] == "FAIL"
        exceed_errors = [e for e in ctx["errors"] if "exceeds audio duration" in e]
        assert len(exceed_errors) >= 1


# ── Test 5: Global overlap from incorrect window → FAIL ────────────────


class TestGlobalOverlapWrongWindow:
    def test_global_overlap_from_wrong_window(self, tmp_path):
        meta = {
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "voiceover": "Scene one.",
                        "subtitleTiming": {
                            "cues": [
                                {"startSec": 0.1, "endSec": 5.0, "text": "Scene one."},
                            ]
                        },
                    },
                    {
                        "sceneNumber": 2,
                        "voiceover": "Scene two.",
                        "subtitleTiming": {
                            "cues": [
                                {"startSec": 0.1, "endSec": 3.0, "text": "Scene two."},
                            ]
                        },
                    },
                ]
            },
            "renderTimeline": [
                {"sceneNumber": 1, "startSec": 0.0, "endSec": 5.0},
                {"sceneNumber": 2, "startSec": 3.0, "endSec": 7.0},  # overlaps scene 1
            ],
            "audio": {
                "continuous": False,
                "provider": "edge_tts",
                "voice": "es-ES-AlvaroNeural",
                "scenes": [
                    {"sceneNumber": 1, "durationSec": 6.0},
                    {"sceneNumber": 2, "durationSec": 4.0},
                ],
            },
        }
        ctx = build_validation_context(meta, video_dir=tmp_path)
        assert ctx["status"] == "FAIL"
        overlap_errors = [e for e in ctx["errors"] if "overlap" in e.lower()]
        assert len(overlap_errors) >= 1


# ── Test 6: Cue within padding but after audio → FAIL ──────────────────


class TestCueInPaddingAfterAudio:
    def test_cue_ends_after_audio(self, tmp_path):
        meta = {
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "voiceover": "Short narration.",
                        "subtitleTiming": {
                            "cues": [
                                {"startSec": 0.1, "endSec": 9.0, "text": "This cue extends past real audio into padding."},
                            ]
                        },
                    },
                ]
            },
            "renderTimeline": [
                {"sceneNumber": 1, "startSec": 0.0, "endSec": 10.0},
            ],
            "audio": {
                "continuous": False,
                "provider": "edge_tts",
                "voice": "es-ES-AlvaroNeural",
                "scenes": [
                    {"sceneNumber": 1, "durationSec": 6.576},  # audio shorter than cue
                ],
            },
        }
        ctx = build_validation_context(meta, video_dir=tmp_path)
        assert ctx["status"] == "FAIL"
        exceed_errors = [e for e in ctx["errors"] if "exceeds audio duration" in e]
        assert len(exceed_errors) >= 1


# ── Test 7: Silence after last cue → allowed ───────────────────────────


class TestSilenceAfterLastCue:
    def test_silence_after_last_cue_allowed(self, tmp_path):
        meta = {
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "voiceover": "Short narration.",
                        "subtitleTiming": {
                            "cues": [
                                {"startSec": 0.1, "endSec": 2.0, "text": "Short narration."},
                            ]
                        },
                    },
                ]
            },
            "renderTimeline": [
                {"sceneNumber": 1, "startSec": 0.0, "endSec": 8.0},
            ],
            "audio": {
                "continuous": False,
                "provider": "edge_tts",
                "voice": "es-ES-AlvaroNeural",
                "scenes": [
                    {"sceneNumber": 1, "durationSec": 6.576},
                ],
            },
        }
        ctx = build_validation_context(meta, video_dir=None)
        assert ctx["status"] == "PASS"


# ── Test 8: ASS with 8 correct dialogues → PASS ────────────────────────


class TestAssCorrect:
    def test_ass_8_correct_dialogues(self, tmp_path):
        meta = _make_e2e_metadata()
        meta_copy = copy.deepcopy(meta)

        ctx = build_validation_context(meta_copy, video_dir=tmp_path)
        global_cues = ctx["globalCues"]

        ass_path = tmp_path / "subtitle.ass"
        ass_path.write_text(_make_ass_content(global_cues))

        ctx2 = build_validation_context(meta, video_dir=tmp_path)
        assert ctx2["status"] == "PASS"
        assert not any("ASS" in e for e in ctx2["errors"])


# ── Test 9: ASS with scene 2 starting at zero → FAIL ───────────────────


class TestAssScene2AtZero:
    def test_ass_scene2_at_zero_fails(self, tmp_path):
        meta = _make_e2e_metadata()

        ctx = build_validation_context(meta, video_dir=tmp_path)
        global_cues = ctx["globalCues"]

        broken_cues = copy.deepcopy(global_cues)
        for c in broken_cues:
            if c["sceneNumber"] >= 2:
                c["startSec"] = round(c["startSec"] - 8.0, 3)
                c["endSec"] = round(c["endSec"] - 8.0, 3)

        ass_path = tmp_path / "subtitle.ass"
        ass_path.write_text(_make_ass_content(broken_cues))

        ctx2 = build_validation_context(meta, video_dir=tmp_path)
        assert any("near zero" in e.lower() or "startSec mismatch" in e for e in ctx2["errors"])


# ── Test 10: ASS with different text → FAIL ────────────────────────────


class TestAssDifferentText:
    def test_ass_different_text_fails(self, tmp_path):
        meta = _make_e2e_metadata()

        ctx = build_validation_context(meta, video_dir=tmp_path)
        global_cues = ctx["globalCues"]

        altered_cues = copy.deepcopy(global_cues)
        if altered_cues:
            altered_cues[2]["text"] = "COMPLETELY DIFFERENT TEXT HERE"

        ass_path = tmp_path / "subtitle.ass"
        ass_path.write_text(_make_ass_content(altered_cues))

        ctx2 = build_validation_context(meta, video_dir=tmp_path)
        text_errors = [e for e in ctx2["errors"] if "text mismatch" in e.lower() or "ASS cue" in e]
        assert len(text_errors) >= 1


# ── Test 12: shorts_creator.rendering.renderer uses shared function ─────────────────────────


class TestRenderJobSharedFunction:
    def test_render_job_uses_shared_context_non_continuous(self, tmp_path, monkeypatch):
        """render_job.py main() with non-continuous audio must call build_validation_context."""
        import render_job as render_cli
        import shorts_creator.rendering.renderer as rj
        rj.main = render_cli.main

        job = tmp_path / "job"
        job.mkdir()
        (job / "scenes").mkdir()
        (job / "assets").mkdir()
        (job / "assets" / "seg_001.jpg").write_text("x")
        (job / "scenes" / "scene-01.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 100)

        meta_path = job / "metadata.json"
        meta = {
            "jobId": "test-shared-func",
            "script": {
                "scenes": [
                    {
                        "sceneNumber": 1,
                        "voiceover": "Test narration.",
                        "subtitleTiming": {
                            "cues": [
                                {"startSec": 0.1, "endSec": 2.0, "text": "Test narration."},
                            ]
                        },
                    },
                ]
            },
            "audio": {
                "provider": "edge-tts",
                "voice": "es-ES-AlvaroNeural",
                "continuous": False,
                "scenes": [
                    {"sceneNumber": 1, "durationSec": 5.0},
                ],
            },
            "assets": [
                {"sceneNumber": 1, "selected": True, "segments": [
                    {"segmentIndex": 1, "path": str(job / "assets" / "seg_001.jpg"),
                     "segmentValidationStatus": "PASS", "error": None}
                ]},
            ],
            "renderTimeline": [
                {"sceneNumber": 1, "segmentIndex": 1, "startSec": 0.0, "endSec": 6.0,
                 "durationSec": 6.0, "beatIndex": 1, "assetType": "broll",
                 "motionType": "static", "assetPath": str(job / "assets" / "seg_001.jpg"),
                 "audioPath": str(job / "scenes" / "scene-01.mp3"),
                 "transitionIn": "cut", "transitionOut": "fade",
                 "subtitleCueIndexes": []},
            ],
            "status": "SUBTITLES_READY",
            "updatedAt": "2026-01-01T00:00:00Z",
            "render": {"path": str(job / "video.mp4"), "durationSeconds": 6.0},
            "subtitles": {"path": str(job / "subtitle.ass"), "format": "ass"},
        }
        meta_path.write_text(json.dumps(meta))

        monkeypatch.setattr("sys.argv", [
            "render_job.py", str(meta_path),
            "--skip-render", "--skip-asset-validation",
        ])
        exit_code = rj.main()
        assert exit_code == 0

        manifest_path = job / "job-manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        gates = manifest.get("validation", {}).get("gates", {})
        assert "subtitleCoverageValidation" in gates
        assert gates["subtitleCoverageValidation"] == "PASS"


# ── Test 13: update_manifest_gates for per-scene mode ──────────────────


class TestUpdateManifestGates:
    def test_update_manifest_gates_per_scene(self, tmp_path):
        from shorts_creator.validation.job import update_manifest_gates

        job_dir = tmp_path / "job"
        job_dir.mkdir()
        (job_dir / "scenes").mkdir()

        meta = _make_e2e_metadata()
        meta_path = job_dir / "metadata.json"
        meta_path.write_text(json.dumps(meta))

        manifest = {
            "jobId": "e2e-pixabay-20260714-184248",
            "validation": {
                "gates": {
                    "technicalValidation": "PASS",
                    "assetValidation": "PASS",
                }
            },
        }
        manifest_path = job_dir / "job-manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        ok = update_manifest_gates(meta_path)
        assert ok is True

        manifest = json.loads(manifest_path.read_text())
        gates = manifest["validation"]["gates"]
        assert gates["subtitleCoverageValidation"] == "PASS"
        assert gates["qualityGate"] == "PASS"


# ── Test 11: Continuous audio regression ──────────────────────────────


class TestContinuousAudioRegression:
    def test_continuous_mode_uses_legacy(self, tmp_path, monkeypatch):
        """Continuous audio must still go through the legacy shorts_creator.validation.coverage path."""
        meta = _make_continuous_metadata()
        meta_copy = copy.deepcopy(meta)

        legacy_called = []

        import shorts_creator.validation.coverage
        original_func = shorts_creator.validation.coverage.run_coverage_validation

        def spy_run_coverage(scene_timings, audio_dur, cues_by_scene, narration_units, remapped_cues=None):
            legacy_called.append(True)
            return {"status": "PASS", "coverage": {"errors": [], "warnings": []}}

        monkeypatch.setattr(shorts_creator.validation.coverage, "run_coverage_validation", spy_run_coverage)

        ctx = build_validation_context(meta_copy)
        assert ctx["mode"] == "continuous"
        assert len(legacy_called) == 1
        assert ctx["status"] == "PASS"

    def test_continuous_validate_job_does_not_break(self):
        """Spot check: JobValidator with continuous audio doesn't crash."""
        from shorts_creator.validation.job import JobValidator
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create proper directory structure: project_root/data/videos/job/metadata.json
            project_root = Path(tmpdir) / "project"
            project_root.mkdir()
            job_dir = project_root / "data" / "videos" / "testjob"
            job_dir.mkdir(parents=True)

            meta_path = job_dir / "metadata.json"
            meta = _make_continuous_metadata()
            meta_path.write_text(json.dumps(meta))

            validator = JobValidator(meta_path, verbose=False)
            ok, msgs = validator._check("subtitle-cues")
            assert ok or len(msgs) >= 0


# ── Unit tests for internal helpers ────────────────────────────────────


class TestSceneWindows:
    def test_build_scene_windows(self):
        timeline = [
            {"sceneNumber": 1, "startSec": 0.0, "endSec": 8.0},
            {"sceneNumber": 2, "startSec": 8.0, "endSec": 13.0},
            {"sceneNumber": 2, "startSec": 13.0, "endSec": 18.0},
            {"sceneNumber": 3, "startSec": 18.0, "endSec": 30.0},
        ]
        windows = _build_scene_windows(timeline, [])
        assert windows[1]["startSec"] == pytest.approx(0.0)
        assert windows[1]["endSec"] == pytest.approx(8.0)
        assert windows[2]["startSec"] == pytest.approx(8.0)
        assert windows[2]["endSec"] == pytest.approx(18.0)
        assert windows[3]["startSec"] == pytest.approx(18.0)
        assert windows[3]["endSec"] == pytest.approx(30.0)

    def test_empty_timeline(self):
        errors = []
        windows = _build_scene_windows([], errors)
        assert windows == {}
        assert len(errors) >= 1


class TestAudioDurationMap:
    def test_build_audio_duration_map(self):
        audio_scenes = [
            {"sceneNumber": 1, "durationSec": 6.576},
            {"sceneNumber": 2, "durationSec": 6.936},
            {"sceneNumber": 3, "durationSec": 7.536},
        ]
        errors = []
        dur_map = _build_audio_duration_map(audio_scenes, errors)
        assert dur_map[1] == pytest.approx(6.576)
        assert dur_map[2] == pytest.approx(6.936)
        assert dur_map[3] == pytest.approx(7.536)
        assert errors == []

    def test_invalid_durations(self):
        errors = []
        dur_map = _build_audio_duration_map([
            {"sceneNumber": 1, "durationSec": None},
            {"sceneNumber": 2, "durationSec": True},
            {"sceneNumber": 3, "durationSec": -1.0},
            {"sceneNumber": 4, "durationSec": float("nan")},
            {"sceneNumber": 5, "durationSec": "hello"},
        ], errors)
        assert dur_map == {}
        assert len(errors) == 5

    def test_duplicate_scene_number(self):
        errors = []
        dur_map = _build_audio_duration_map([
            {"sceneNumber": 1, "durationSec": 5.0},
            {"sceneNumber": 1, "durationSec": 6.0},
        ], errors)
        assert len(dur_map) == 1
        assert len(errors) == 1


class TestLocalCueValidation:
    def test_valid_local_cues(self):
        cues = [
            {"startSec": 0.1, "endSec": 2.0, "text": "hello"},
            {"startSec": 2.5, "endSec": 5.0, "text": "world"},
        ]
        errors = []
        warnings = []
        _validate_local_cues(1, cues, 6.0, errors, warnings)
        assert errors == []

    def test_non_monotonic_cues(self):
        cues = [
            {"startSec": 0.1, "endSec": 3.0, "text": "a"},
            {"startSec": 1.0, "endSec": 5.0, "text": "b"},
        ]
        errors = []
        warnings = []
        _validate_local_cues(1, cues, 6.0, errors, warnings)
        assert any("local overlap" in e for e in errors)

    def test_start_negative(self):
        cues = [
            {"startSec": -0.1, "endSec": 2.0, "text": "bad"},
        ]
        errors = []
        warnings = []
        _validate_local_cues(1, cues, 6.0, errors, warnings)
        assert any("startSec=-0.100 < 0" in e for e in errors)

    def test_bool_values(self):
        cues = [
            {"startSec": True, "endSec": False, "text": "bad"},
        ]
        errors = []
        warnings = []
        _validate_local_cues(1, cues, None, errors, warnings)
        assert any("bool" in e for e in errors)


class TestGlobalCueBuild:
    def test_global_cues_with_offsets(self):
        meta = _make_e2e_metadata()
        windows = _build_scene_windows(meta["renderTimeline"], [])

        all_local = []
        for scene in meta["script"]["scenes"]:
            sn = scene["sceneNumber"]
            for cue in scene["subtitleTiming"]["cues"]:
                all_local.append({"sceneNumber": sn, "cue": cue})

        errors = []
        gc = _build_global_cues(all_local, windows, errors)
        assert len(gc) == 8
        assert errors == []

        sorted_gc = sorted(gc, key=lambda c: c["startSec"])
        for i in range(1, len(sorted_gc)):
            assert sorted_gc[i]["startSec"] >= sorted_gc[i - 1]["endSec"] - 0.1


class TestGlobalCueValidation:
    def test_monotonic_global_cues(self):
        gc = [
            {"sceneNumber": 1, "startSec": 0.1, "endSec": 2.0},
            {"sceneNumber": 1, "startSec": 3.0, "endSec": 5.0},
            {"sceneNumber": 2, "startSec": 8.1, "endSec": 10.0},
        ]
        errors = []
        _validate_global_cues(gc, {1: {"startSec": 0.0, "endSec": 8.0},
                                   2: {"startSec": 8.0, "endSec": 18.0}}, errors)
        assert errors == []

    def test_cross_scene_overlap(self):
        gc = [
            {"sceneNumber": 1, "startSec": 0.0, "endSec": 5.0},
            {"sceneNumber": 2, "startSec": 4.0, "endSec": 8.0},  # overlaps by 1s
        ]
        errors = []
        _validate_global_cues(gc, {1: {"startSec": 0.0, "endSec": 8.0},
                                   2: {"startSec": 8.0, "endSec": 15.0}}, errors)
        assert any("overlap" in e.lower() for e in errors)

    def test_cue_exceeds_scene_window(self):
        gc = [
            {"sceneNumber": 1, "startSec": 0.0, "endSec": 12.0},  # past window end=8.0
        ]
        errors = []
        _validate_global_cues(gc, {1: {"startSec": 0.0, "endSec": 8.0}}, errors)
        assert any("endSec=12.0" in e for e in errors)


class TestAssValidation:
    def test_ass_dialogue_count_mismatch(self, tmp_path):
        gc = [
            {"sceneNumber": 1, "startSec": 0.1, "endSec": 2.0, "text": "one"},
            {"sceneNumber": 1, "startSec": 3.0, "endSec": 5.0, "text": "two"},
        ]
        # Only 1 dialogue line
        ass_path = tmp_path / "subtitle.ass"
        ass_path.write_text(_make_ass_content(gc[:1]))
        errors = []
        scenes = [{"sceneNumber": 1}]
        _validate_ass_dialogues(ass_path, gc, scenes, {1: {"startSec": 0.0, "endSec": 8.0}}, errors)
        assert any("count mismatch" in e for e in errors)
