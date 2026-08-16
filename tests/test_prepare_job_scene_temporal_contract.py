"""Tests for Phase B: per-scene temporal contract in prepare_job.py.

Covers: resolve_scene_window_duration, timeline distribution over sceneWindowSec,
subtitle offsets via generate_ass_from_cues, cue validation.
"""

import json
import math
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import pytest

from shorts_creator.rendering.preparer import (
    resolve_scene_window_duration,
    generate_ass_from_cues,
    fmt_ass_time,
    build_render_timeline,
)


# ---------------------------------------------------------------------------
# resolve_scene_window_duration
# ---------------------------------------------------------------------------


class TestResolveSceneWindowDuration:
    def test_basic_adds_default_tail(self):
        assert resolve_scene_window_duration(4.0) == pytest.approx(4.35, abs=0.01)

    def test_audio_6_5_tail_0_35_returns_6_85(self):
        assert resolve_scene_window_duration(6.576, 0.35) == pytest.approx(6.926)

    def test_audio_5_tail_0_returns_5(self):
        assert resolve_scene_window_duration(5.0, 0.0) == 5.0

    def test_audio_5_tail_0_5_returns_5_5(self):
        assert resolve_scene_window_duration(5.0, 0.5) == 5.5

    def test_custom_tail_pause(self):
        assert resolve_scene_window_duration(10.0, 0.60) == pytest.approx(10.6)

    def test_audio_zero_raises(self):
        with pytest.raises(ValueError, match="positive"):
            resolve_scene_window_duration(0.0)

    def test_audio_negative_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            resolve_scene_window_duration(-1.0)

    def test_tail_exceeds_1_raises(self):
        with pytest.raises(ValueError, match="1.0"):
            resolve_scene_window_duration(5.0, 2.0)

    def test_nan_audio_raises(self):
        with pytest.raises(ValueError, match="finite"):
            resolve_scene_window_duration(float("nan"))

    def test_nan_tail_raises(self):
        with pytest.raises(ValueError, match="finite"):
            resolve_scene_window_duration(5.0, float("nan"))

    def test_inf_audio_raises(self):
        with pytest.raises(ValueError, match="finite"):
            resolve_scene_window_duration(float("inf"))

    def test_inf_tail_raises(self):
        with pytest.raises(ValueError, match="finite"):
            resolve_scene_window_duration(5.0, float("inf"))

    def test_bool_audio_raises(self):
        with pytest.raises(TypeError, match="bool"):
            resolve_scene_window_duration(True)

    def test_bool_tail_raises(self):
        with pytest.raises(TypeError, match="bool"):
            resolve_scene_window_duration(5.0, False)

    def test_str_audio_raises(self):
        with pytest.raises(TypeError, match="int or float"):
            resolve_scene_window_duration("8")

    def test_none_audio_raises(self):
        with pytest.raises(TypeError, match="int or float"):
            resolve_scene_window_duration(None)

    def test_returns_float(self):
        result = resolve_scene_window_duration(8.0)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Timeline distribution over sceneWindowSec
# ---------------------------------------------------------------------------


class TestTimelineSceneWindowDistribution:
    def test_two_segments_even_split_10s(self, tmp_path):
        """Scene of 10s with two segments at 0.5/0.5 produces 5/5."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 10, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": 0.5, "path": "a.jpg"},
                {"segmentIndex": 2, "durationFraction": 0.5, "path": "b.jpg"},
            ],
        }]

        rt = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 9.65})
        entries = [e for e in rt if e["sceneNumber"] == 1]
        assert len(entries) == 2
        assert entries[0]["durationSec"] == pytest.approx(5.0, abs=0.1)
        assert entries[1]["durationSec"] == pytest.approx(5.0, abs=0.1)

    def test_scene_window_longer_than_target_redistributes(self, tmp_path):
        """When audio is longer, scene window expands and segments redistribute."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 6, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": 0.5, "path": "a.jpg"},
                {"segmentIndex": 2, "durationFraction": 0.5, "path": "b.jpg"},
            ],
        }]

        rt = build_render_timeline(
            scenes, assets, scenes_dir,
            scene_audio_durations={1: 7.5},
        )
        entries = [e for e in rt if e["sceneNumber"] == 1]
        assert len(entries) == 2
        window = 7.5 + 0.35
        assert entries[0]["durationSec"] == pytest.approx(window / 2, abs=0.1)
        assert entries[1]["durationSec"] == pytest.approx(window / 2, abs=0.1)
        total = entries[1]["endSec"] - entries[0]["startSec"]
        assert total == pytest.approx(window, abs=0.1)

    def test_three_scenes_contiguous(self, tmp_path):
        """Three scenes produce contiguous timeline with no gaps or overlaps."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        for i in range(1, 4):
            (scenes_dir / f"scene-{i:02}.mp3").write_text("audio")

        scenes = [
            {"sceneNumber": 1, "targetDurationSec": 8, "subtitleTiming": {"cues": []}},
            {"sceneNumber": 2, "targetDurationSec": 10, "subtitleTiming": {"cues": []}},
            {"sceneNumber": 3, "targetDurationSec": 12, "subtitleTiming": {"cues": []}},
        ]
        assets = [
            {"sceneNumber": 1, "segments": [
                {"segmentIndex": 1, "durationFraction": 0.5, "path": "a1.jpg"},
                {"segmentIndex": 2, "durationFraction": 0.5, "path": "a2.jpg"}]},
            {"sceneNumber": 2, "segments": [
                {"segmentIndex": 1, "durationFraction": 0.5, "path": "b1.jpg"},
                {"segmentIndex": 2, "durationFraction": 0.5, "path": "b2.jpg"}]},
            {"sceneNumber": 3, "segments": [
                {"segmentIndex": 1, "durationFraction": 0.5, "path": "c1.jpg"},
                {"segmentIndex": 2, "durationFraction": 0.5, "path": "c2.jpg"}]},
        ]

        rt = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 7.65, 2: 9.65, 3: 11.65})
        timeline = sorted(rt, key=lambda e: e["startSec"])

        # Check monotonic endSec
        for i in range(len(timeline) - 1):
            assert timeline[i]["endSec"] <= timeline[i + 1]["startSec"] + 0.01
        # No gaps > 0.05s
        for i in range(len(timeline) - 1):
            gap = timeline[i + 1]["startSec"] - timeline[i]["endSec"]
            assert gap <= 0.05, f"gap of {gap:.3f}s between entries {i} and {i+1}"

    def test_sum_equals_scene_window_with_last_segment_adjustment(self, tmp_path):
        """Sum of segment durations equals sceneWindowSec when using durationFraction."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [
            {"sceneNumber": 1, "targetDurationSec": 10, "subtitleTiming": {"cues": []}},
        ]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": 0.33, "path": "a.jpg"},
                {"segmentIndex": 2, "durationFraction": 0.33, "path": "b.jpg"},
                {"segmentIndex": 3, "durationFraction": 0.34, "path": "c.jpg"},
            ],
        }]

        rt = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 9.65})
        entries = [e for e in rt if e["sceneNumber"] == 1]
        total = sum(e["durationSec"] for e in entries)
        assert total == pytest.approx(10.0, abs=0.1)

    def test_single_segment_no_regression(self, tmp_path):
        """Single segment per scene still works with scene window."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 8, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": 1.0, "path": "a.jpg"},
            ],
        }]

        rt = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 7.65})
        entries = [e for e in rt if e["sceneNumber"] == 1]
        assert len(entries) == 1
        assert entries[0]["durationSec"] == pytest.approx(8.0, abs=0.1)

    def test_v2_assets_paths_preserved_with_scene_window(self, tmp_path):
        """V2 namespaced asset paths preserved when using scene window."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 10, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": 1.0,
                 "path": "assets/scene_001_seg_001.jpg"},
            ],
        }]

        rt = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 9.65})
        assert rt[0]["assetPath"] == "assets/scene_001_seg_001.jpg"


# ---------------------------------------------------------------------------
# Subtitle offsets via generate_ass_from_cues
# ---------------------------------------------------------------------------


def _make_cue(start, end, text, scene_number=None):
    return {"startSec": start, "endSec": end, "text": text,
            "sceneNumber": scene_number}


class TestSubtitleSceneOffsets:
    def test_local_cues_become_global_with_offsets(self, tmp_path):
        """Three scenes, cues start at 0 locally, offsets make them global."""
        ass_path = tmp_path / "out.ass"
        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": [
                _make_cue(0.0, 2.0, "Scene 1 cue"),
            ]}},
            {"sceneNumber": 2, "subtitleTiming": {"cues": [
                _make_cue(0.0, 2.5, "Scene 2 cue"),
            ]}},
            {"sceneNumber": 3, "subtitleTiming": {"cues": [
                _make_cue(0.0, 3.0, "Scene 3 cue"),
            ]}},
        ]
        offsets = {1: 0.0, 2: 8.0, 3: 18.0}

        generate_ass_from_cues(scenes, ass_path, style_name="shorts_upper_dynamic",
                               scene_offsets=offsets)
        content = ass_path.read_text()
        lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
        assert len(lines) == 3

    def test_times_are_global_after_offset(self, tmp_path):
        """Cue times in ASS must be (local + offset)."""
        ass_path = tmp_path / "out.ass"
        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": [
                _make_cue(1.5, 3.5, "Testing"),
            ]}},
        ]
        offsets = {1: 10.0}

        generate_ass_from_cues(scenes, ass_path, style_name="shorts_upper_dynamic",
                               scene_offsets=offsets)
        content = ass_path.read_text()
        for line in content.splitlines():
            if line.startswith("Dialogue:"):
                parts = line.split(",")
                start_time = parts[1]
                end_time = parts[2]
                # 1.5 + 10 = 11.5s
                assert "0:00:11" in start_time, f"Expected ~11.5s, got {start_time}"
                assert "0:00:13" in end_time, f"Expected ~13.5s, got {end_time}"

    def test_no_double_offset_for_continuous(self, tmp_path):
        """Without scene_offsets, cues are written verbatim (continuous mode)."""
        ass_path = tmp_path / "out.ass"
        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": [
                _make_cue(5.0, 7.0, "Global cue"),
            ]}},
        ]

        generate_ass_from_cues(scenes, ass_path, style_name="shorts_upper_dynamic")
        content = ass_path.read_text()
        for line in content.splitlines():
            if line.startswith("Dialogue:"):
                parts = line.split(",")
                start_time = parts[1]
                assert "0:00:05" in start_time, f"Expected ~5.0s, got {start_time}"

    def test_original_cues_not_mutated(self, tmp_path):
        """Original cue dicts must not be modified by generate_ass_from_cues."""
        original = _make_cue(1.0, 2.0, "Pristine")
        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": [original]}},
        ]
        offsets = {1: 5.0}
        ass_path = tmp_path / "out.ass"

        generate_ass_from_cues(scenes, ass_path, style_name="shorts_upper_dynamic",
                               scene_offsets=offsets)
        assert original["startSec"] == 1.0
        assert original["endSec"] == 2.0

    def test_missing_offset_raises(self, tmp_path):
        """Scene with cues but no offset must raise ValueError."""
        ass_path = tmp_path / "out.ass"
        scenes = [
            {"sceneNumber": 2, "subtitleTiming": {"cues": [
                _make_cue(0.0, 1.0, "No offset"),
            ]}},
        ]
        offsets = {1: 0.0}  # scene 2 missing

        with pytest.raises(ValueError, match="scene_offsets missing"):
            generate_ass_from_cues(scenes, ass_path, style_name="shorts_upper_dynamic",
                                   scene_offsets=offsets)

    def test_empty_cues_scene_skips_offset_check(self, tmp_path):
        """Scene without cues doesn't trigger missing offset error."""
        ass_path = tmp_path / "out.ass"
        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": []}},
            {"sceneNumber": 2, "subtitleTiming": {"cues": [
                _make_cue(0.0, 1.0, "Has offset"),
            ]}},
        ]
        offsets = {2: 5.0}  # scene 1 not present, but has no cues

        generate_ass_from_cues(scenes, ass_path, style_name="shorts_upper_dynamic",
                               scene_offsets=offsets)
        content = ass_path.read_text()
        lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
        assert len(lines) == 1

    def test_backward_compatible_no_offsets(self, tmp_path):
        """Call without scene_offsets preserves original behavior."""
        ass_path = tmp_path / "out.ass"
        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": [
                _make_cue(2.0, 4.0, "Old style"),
            ]}},
        ]
        generate_ass_from_cues(scenes, ass_path, style_name="shorts_upper_dynamic")
        content = ass_path.read_text()
        assert "Dialogue:" in content


# ---------------------------------------------------------------------------
# Integration: shorts_creator.rendering.preparer main with scene window
# ---------------------------------------------------------------------------


class TestMainSceneWindowIntegration:
    def test_non_continuous_scene_window_in_timeline(self, monkeypatch, tmp_path):
        import prepare_job as prepare_cli
        import shorts_creator.rendering.preparer as pj
        pj.main = prepare_cli.main

        job = tmp_path / "job"
        job.mkdir()
        scenes_dir = job / "scenes"
        scenes_dir.mkdir()
        img = job / "scenes" / "scene-01-01.jpg"
        img.write_text("x" * 1000)
        img2 = job / "scenes" / "scene-01-02.jpg"
        img2.write_text("x" * 1000)
        mp3 = scenes_dir / "scene-01.mp3"
        mp3.write_text("x" * 2000)
        meta_path = job / "metadata.json"

        meta = {
            "jobId": "test-sw-001",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 6.0,
                 "voiceover": "Test.", "subtitle": "Test",
                 "subtitleTiming": {"cues": [
                     {"startSec": 0.0, "endSec": 2.0, "text": "cue1"},
                 ]},
                 "visualPlan": {
                     "editorialRole": "context_map",
                     "visualSequence": [
                         {"segmentIndex": 1, "assetType": "historical_map",
                          "durationFraction": 0.5},
                         {"segmentIndex": 2, "assetType": "document",
                          "durationFraction": 0.5},
                     ],
                 }},
            ]},
            "audio": {
                "provider": "edge-tts",
                "continuous": False,
                "duration_estimated": False,
                "scenes": [
                    {"sceneNumber": 1, "path": str(mp3), "exists": True,
                     "durationSec": 6.936, "durationSource": "ffprobe_local"},
                ],
            },
            "assets": [{
                "sceneNumber": 1, "selected": True,
                "segments": [
                    {"segmentIndex": 1, "path": str(img),
                     "segmentValidationStatus": "PASS", "error": None},
                    {"segmentIndex": 2, "path": str(img2),
                     "segmentValidationStatus": "PASS", "error": None},
                ],
            }],
        }
        meta_path.write_text(json.dumps(meta))

        monkeypatch.setattr(sys, "argv", ["prepare_job.py", str(meta_path)])
        exit_code = pj.main()
        assert exit_code == 0

        result = json.loads(meta_path.read_text())
        assert result["status"] == "SUBTITLES_READY"
        rt = result["renderTimeline"]
        entries = [e for e in rt if e["sceneNumber"] == 1]
        assert len(entries) == 2
        total = sum(e["durationSec"] for e in entries)
        assert total == pytest.approx(7.286, abs=0.2)

    def test_scene_offset_used_in_ass(self, monkeypatch, tmp_path):
        """Subtitle cues must be globally offset in non-continuous mode."""
        import prepare_job as prepare_cli
        import shorts_creator.rendering.preparer as pj
        pj.main = prepare_cli.main

        job = tmp_path / "job"
        job.mkdir()
        scenes_dir = job / "scenes"
        scenes_dir.mkdir()
        img = job / "scenes" / "scene-01-01.jpg"
        img.write_text("x" * 1000)
        img2 = job / "scenes" / "scene-02-01.jpg"
        img2.write_text("x" * 1000)
        mp3_1 = scenes_dir / "scene-01.mp3"
        mp3_1.write_text("x" * 2000)
        mp3_2 = scenes_dir / "scene-02.mp3"
        mp3_2.write_text("x" * 2000)
        meta_path = job / "metadata.json"

        meta = {
            "jobId": "test-offset-001",
            "script": {"scenes": [
                {"sceneNumber": 1, "targetDurationSec": 5.0,
                 "voiceover": "Scene one text.", "subtitle": "S1",
                 "subtitleTiming": {"cues": [
                     {"startSec": 0.0, "endSec": 2.0, "text": "Scene one text."},
                 ]}},
                {"sceneNumber": 2, "targetDurationSec": 5.0,
                 "voiceover": "Scene two text.", "subtitle": "S2",
                 "subtitleTiming": {"cues": [
                     {"startSec": 0.0, "endSec": 2.0, "text": "Scene two text."},
                 ]}},
            ]},
            "audio": {
                "provider": "edge-tts",
                "continuous": False,
                "duration_estimated": False,
                "scenes": [
                    {"sceneNumber": 1, "path": str(mp3_1), "exists": True,
                     "durationSec": 4.5, "durationSource": "ffprobe_local"},
                    {"sceneNumber": 2, "path": str(mp3_2), "exists": True,
                     "durationSec": 4.5, "durationSource": "ffprobe_local"},
                ],
            },
            "assets": [
                {"sceneNumber": 1, "selected": True,
                 "segments": [{"segmentIndex": 1, "path": str(img),
                               "segmentValidationStatus": "PASS", "error": None}]},
                {"sceneNumber": 2, "selected": True,
                 "segments": [{"segmentIndex": 1, "path": str(img2),
                               "segmentValidationStatus": "PASS", "error": None}]},
            ],
        }
        meta_path.write_text(json.dumps(meta))

        monkeypatch.setattr(sys, "argv", ["prepare_job.py", str(meta_path)])
        exit_code = pj.main()
        assert exit_code == 0

        ass_path = job / "subtitle.ass"
        content = ass_path.read_text()
        dialogue_lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
        assert len(dialogue_lines) == 2

        # Scene 2 cues should start around 4.85s (scene 1 window = 4.5 + 0.35)
        scene2_line = dialogue_lines[1]
        parts = scene2_line.split(",")
        start = parts[1]


# ---------------------------------------------------------------------------
# DurationFraction normalization
# ---------------------------------------------------------------------------


class TestDurationFractionNormalization:
    def test_fractions_normalized_to_one(self, tmp_path):
        """Fractions 0.2 + 0.2 normalized → 0.5 + 0.5."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 10, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": 0.2, "path": "a.jpg"},
                {"segmentIndex": 2, "durationFraction": 0.2, "path": "b.jpg"},
            ],
        }]

        rt = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 9.65})
        entries = [e for e in rt if e["sceneNumber"] == 1]
        assert len(entries) == 2
        assert entries[0]["durationSec"] == pytest.approx(5.0, abs=0.1)
        assert entries[1]["durationSec"] == pytest.approx(5.0, abs=0.1)
        total = entries[1]["endSec"] - entries[0]["startSec"]
        assert total == pytest.approx(10.0, abs=0.01)

    def test_fractions_2_1_normalized(self, tmp_path):
        """Fractions 2 + 1 → 2/3 + 1/3."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 9, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": 2, "path": "a.jpg"},
                {"segmentIndex": 2, "durationFraction": 1, "path": "b.jpg"},
            ],
        }]

        rt = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 8.65})
        entries = [e for e in rt if e["sceneNumber"] == 1]
        assert entries[0]["durationSec"] == pytest.approx(6.0, abs=0.1)
        assert entries[1]["durationSec"] == pytest.approx(3.0, abs=0.1)

    def test_non_continuous_scene_window_in_timeline(self, tmp_path):
        """Scene with audio > targetDurationSec should use audio + tail, not target."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 6, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": 1, "path": "a.jpg"},
            ],
        }]

        rt = build_render_timeline(
            scenes, assets, scenes_dir,
            scene_audio_durations={1: 7.536},
        )
        window = 7.536 + 0.35
        entries = [e for e in rt if e["sceneNumber"] == 1]
        assert len(entries) == 1
        assert entries[0]["startSec"] == pytest.approx(0.0, abs=0.001)
        assert entries[0]["endSec"] == pytest.approx(window, abs=0.001)
        assert entries[0]["endSec"] - entries[0]["startSec"] == pytest.approx(window, abs=0.001)

    def test_last_segment_absorbs_rounding(self, tmp_path):
        """Last segment end equals scene_offset + scene_duration."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 7.5, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": 1, "path": "a.jpg"},
            ],
        }]

        rt = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 7.536})
        window = 7.536 + 0.35
        entries = [e for e in rt if e["sceneNumber"] == 1]
        assert len(entries) == 1
        assert entries[0]["startSec"] == pytest.approx(0.0, abs=0.001)
        assert entries[0]["endSec"] == pytest.approx(window, abs=0.001)
        assert entries[0]["endSec"] - entries[0]["startSec"] == pytest.approx(window, abs=0.001)

    def test_three_segments_last_closes_exactly(self, tmp_path):
        """Three segments, last segment end = scene window start + scene_duration."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 10, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": 0.1, "path": "a.jpg"},
                {"segmentIndex": 2, "durationFraction": 0.2, "path": "b.jpg"},
                {"segmentIndex": 3, "durationFraction": 0.7, "path": "c.jpg"},
            ],
        }]

        rt = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 9.65})
        entries = [e for e in rt if e["sceneNumber"] == 1]
        assert len(entries) == 3
        total = entries[-1]["endSec"] - entries[0]["startSec"]
        assert total == pytest.approx(10.0, abs=0.01)

    def test_invalid_fraction_nan_raises(self, tmp_path):
        """NaN durationFraction raises ValueError."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 10, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": float("nan"), "path": "a.jpg"},
            ],
        }]

        with pytest.raises(ValueError, match="finite"):
            build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 9.65})

    def test_invalid_fraction_zero_raises(self, tmp_path):
        """Zero durationFraction raises ValueError."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 10, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": 0, "path": "a.jpg"},
            ],
        }]

        with pytest.raises(ValueError, match="positive"):
            build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 9.65})

    def test_invalid_fraction_negative_raises(self, tmp_path):
        """Negative durationFraction raises ValueError."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 10, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": -1, "path": "a.jpg"},
            ],
        }]

        with pytest.raises(ValueError, match="positive"):
            build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 9.65})

    def test_invalid_fraction_string_raises(self, tmp_path):
        """String durationFraction raises ValueError."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 10, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 1, "durationFraction": "half", "path": "a.jpg"},
            ],
        }]

        with pytest.raises(ValueError, match="numeric"):
            build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 9.65})

    def test_segment_index_not_consecutive_still_works(self, tmp_path):
        """segments with non-consecutive segmentIndex still distribute correctly."""
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        (scenes_dir / "scene-01.mp3").write_text("audio")

        scenes = [{"sceneNumber": 1, "targetDurationSec": 10, "subtitleTiming": {"cues": []}}]
        assets = [{
            "sceneNumber": 1,
            "segments": [
                {"segmentIndex": 5, "durationFraction": 0.5, "path": "a.jpg"},
                {"segmentIndex": 7, "durationFraction": 0.5, "path": "b.jpg"},
            ],
        }]

        rt = build_render_timeline(scenes, assets, scenes_dir, scene_audio_durations={1: 9.65})
        entries = [e for e in rt if e["sceneNumber"] == 1]
        assert len(entries) == 2
        total = entries[-1]["endSec"] - entries[0]["startSec"]
        assert total == pytest.approx(10.0, abs=0.01)


# ---------------------------------------------------------------------------
# Cue validation (resolve_and_validate_global_cues)
# ---------------------------------------------------------------------------


class TestCueValidation:
    def test_valid_cues_pass_validation(self):
        """Three scenes with valid local cues produce correct global cues."""
        from shorts_creator.rendering.preparer import resolve_and_validate_global_cues

        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": [
                {"startSec": 0.0, "endSec": 2.0, "text": "c1"},
            ]}},
            {"sceneNumber": 2, "subtitleTiming": {"cues": [
                {"startSec": 0.0, "endSec": 3.0, "text": "c2"},
            ]}},
        ]
        offsets = {1: 0.0, 2: 8.0}
        windows = {1: (0.0, 8.0), 2: (8.0, 18.0)}

        global_cues = resolve_and_validate_global_cues(
            scenes, offsets, windows
        )
        assert len(global_cues) == 2
        assert global_cues[0]["startSec"] == 0.0
        assert global_cues[1]["startSec"] == 8.0

    def test_cue_outside_window_raises(self):
        """Cue that exceeds scene window after offset → ValueError."""
        from shorts_creator.rendering.preparer import resolve_and_validate_global_cues

        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": [
                {"startSec": 0.0, "endSec": 9.0, "text": "too long"},
            ]}},
        ]
        offsets = {1: 0.0}
        windows = {1: (0.0, 8.0)}

        with pytest.raises(ValueError, match="scene window"):
            resolve_and_validate_global_cues(scenes, offsets, windows)

    def test_cross_scene_overlap_raises(self):
        """Cues from different scenes that overlap globally → ValueError."""
        from shorts_creator.rendering.preparer import resolve_and_validate_global_cues

        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": [
                {"startSec": 0.0, "endSec": 8.5, "text": "c1"},
            ]}},
            {"sceneNumber": 2, "subtitleTiming": {"cues": [
                {"startSec": 0.0, "endSec": 2.0, "text": "c2"},
            ]}},
        ]
        offsets = {1: 0.0, 2: 8.0}
        windows = {1: (0.0, 8.5), 2: (8.0, 10.0)}

        with pytest.raises(ValueError, match="cross-scene"):
            resolve_and_validate_global_cues(scenes, offsets, windows)

    def test_nan_start_rejected(self):
        """NaN startSec → ValueError."""
        from shorts_creator.rendering.preparer import resolve_and_validate_global_cues

        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": [
                {"startSec": float("nan"), "endSec": 2.0, "text": "bad"},
            ]}},
        ]
        offsets = {1: 0.0}
        windows = {1: (0.0, 8.0)}

        with pytest.raises(ValueError, match="finite"):
            resolve_and_validate_global_cues(scenes, offsets, windows)

    def test_negative_start_rejected(self):
        """Negative startSec after offset → ValueError."""
        from shorts_creator.rendering.preparer import resolve_and_validate_global_cues

        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": [
                {"startSec": 1.0, "endSec": 3.0, "text": "bad"},
            ]}},
        ]
        offsets = {1: -2.0}
        windows = {1: (-1.0, 5.0)}

        with pytest.raises(ValueError, match="< 0"):
            resolve_and_validate_global_cues(scenes, offsets, windows)

    def test_end_le_start_rejected(self):
        """endSec <= startSec → ValueError."""
        from shorts_creator.rendering.preparer import resolve_and_validate_global_cues

        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": [
                {"startSec": 5.0, "endSec": 3.0, "text": "backward"},
            ]}},
        ]
        offsets = {1: 0.0}
        windows = {1: (0.0, 8.0)}

        with pytest.raises(ValueError, match="<="):
            resolve_and_validate_global_cues(scenes, offsets, windows)

    def test_original_cues_not_mutated_by_validation(self):
        """Validation must not modify the original cue dicts."""
        from shorts_creator.rendering.preparer import resolve_and_validate_global_cues

        original = {"startSec": 0.0, "endSec": 2.0, "text": "pristine"}
        scenes = [
            {"sceneNumber": 1, "subtitleTiming": {"cues": [original]}},
        ]
        offsets = {1: 5.0}
        windows = {1: (5.0, 7.0)}

        resolve_and_validate_global_cues(scenes, offsets, windows)
        assert original["startSec"] == 0.0
        assert original["endSec"] == 2.0

    def test_continuous_mode_returns_none(self):
        """scene_offsets=None returns None (no validation for continuous)."""
        from shorts_creator.rendering.preparer import resolve_and_validate_global_cues

        scenes = [{"sceneNumber": 1, "subtitleTiming": {"cues": []}}]
        result = resolve_and_validate_global_cues(scenes, None, None)
        assert result is None
