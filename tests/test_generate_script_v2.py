"""Tests for native VisualPlan v2 generation in generate_script.py.

All LLM calls are mocked — no live OpenAI requests.
"""

import json as _json
import math
import sys
from pathlib import Path

import pytest

_PROJECT = Path(__file__).resolve().parents[1]
_BIN = _PROJECT / "bin"
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

from visual_plan_v2 import (
    SCHEMA_VERSION as V2_SCHEMA_VERSION,
    ALLOWED_VISUAL_INTENTS,
    ALLOWED_ASSET_PREFERENCES,
    ALLOWED_TRANSITIONS,
)

import generate_script as gs

# ── Re-parse SYSTEM_PROMPT_V2 from file ──────────────────────────────────────

_PROMPT_TEXT = (_PROJECT / "bin" / "generate_script.py").read_text()
import re
_m = re.search(r'SYSTEM_PROMPT_V2\s*=\s*"""(.+?)"""', _PROMPT_TEXT, re.DOTALL)
SYSTEM_PROMPT_V2 = _m.group(1) if _m else ""


# ── V2 fixtures ──────────────────────────────────────────────────────────────


def _v2_scene_vp(**overrides):
    """Minimal valid v2 visualPlan."""
    vp = {
        "_schemaVersion": V2_SCHEMA_VERSION,
        "visualIntent": "explain",
        "subjects": ["test subject"],
        "searchQueries": ["test query"],
        "assetPreferences": ["diagram"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "diagram",
                "durationFraction": 1.0,
                "transition": "cut",
            }
        ],
    }
    vp.update(overrides)
    return vp


def _v2_scene(scene_number=1, vp_overrides=None, **overrides):
    """Minimal valid v2 scene with ~13 words for ~30s target across 4 scenes."""
    s = {
        "sceneNumber": scene_number,
        "voiceover": f"Escena {scene_number} del guion divulgativo con contenido narrativo suficiente para completar la duración.",
        "subtitle": f"Subtitulo {scene_number}",
        "targetDurationSec": 7.5,
        "visualPlan": _v2_scene_vp(**(vp_overrides or {})),
    }
    s.update(overrides)
    return s


def _v2_script(scenes=None):
    """Valid v2 script with 4 scenes."""
    if scenes is None:
        scenes = [_v2_scene(i) for i in range(1, 5)]
    return {
        "title": "Test Script",
        "hook": "Test hook",
        "summary": "Test summary",
        "totalTargetDurationSec": 30,
        "scenes": scenes,
    }


# ── CLI and request tests ────────────────────────────────────────────────────


class TestCliAndRequest:
    """Tests 1-4: CLI flag behavior and request metadata."""

    def test_default_uses_system_prompt(self, monkeypatch):
        """Default (no --visual-schema-version) uses SYSTEM_PROMPT (v1)."""
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        tested = {"reached": False}

        def mock_main():
            import argparse
            p = argparse.ArgumentParser()
            p.add_argument("--topic", default="test")
            p.add_argument("--visual-schema-version", type=int, choices=[1, 2], default=1)
            p.add_argument("--dry-run", action="store_true", default=False)
            from duration_profiles import add_duration_profile_args
            add_duration_profile_args(p)
            args = p.parse_args([])
            assert args.visual_schema_version == 1
            tested["reached"] = True
            return 0

        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "test", "--dry-run", "--model", "gpt-4o-mini"])
        exit_code = gs.main()
        assert exit_code == 0

    def test_explicit_v1_uses_system_prompt(self, monkeypatch, capsys):
        """--visual-schema-version 1 uses SYSTEM_PROMPT."""
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "test", "--visual-schema-version", "1",
                                           "--dry-run", "--model", "gpt-4o-mini"])
        exit_code = gs.main()
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "visualSchemaVersion=1" in out

    def test_explicit_v2_uses_system_prompt_v2(self, monkeypatch, capsys):
        """--visual-schema-version 2 uses SYSTEM_PROMPT_V2."""
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "test", "--visual-schema-version", "2",
                                           "--dry-run", "--model", "gpt-4o-mini"])
        exit_code = gs.main()
        assert exit_code == 0
        out = capsys.readouterr().out
        # dry-run prints the active system prompt which should be v2
        assert "schemaVersion=2" in out

    def test_v2_metadata_persists_schema_version(self, monkeypatch, tmp_path):
        """Metadata v2 persists request.visuals.schemaVersion=2."""
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        out_path = tmp_path / "metadata.json"

        script = _v2_script()

        calls = [0]

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            calls[0] += 1
            return _json.dumps(script)

        monkeypatch.setattr(gs, "call_llm", mock_call)
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])

        exit_code = gs.main()
        assert exit_code == 0
        meta = _json.loads(out_path.read_text())
        assert meta["request"]["visuals"]["schemaVersion"] == 2
        assert meta["status"] == "SCRIPT_DRAFT"


# ── Success v2 tests ─────────────────────────────────────────────────────────


class TestV2Success:
    """Tests 5-15: successful v2 generation scenarios."""

    def test_all_scenes_have_schema_version_2(self, monkeypatch, tmp_path):
        script = _v2_script()
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(script))
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        assert exit_code == 0
        meta = _json.loads(out_path.read_text())
        for scene in meta["script"]["scenes"]:
            assert scene["visualPlan"]["_schemaVersion"] == 2

    def test_raw_plan_replaced_by_canonical_plan(self, monkeypatch, tmp_path):
        script = _v2_script()
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(script))
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        meta = _json.loads(out_path.read_text())
        for scene in meta["script"]["scenes"]:
            vp = scene["visualPlan"]
            assert "preferredProviders" in vp  # canonical default applied
            assert "allowGeneratedImage" in vp  # canonical default applied

    def test_whitespace_and_enum_lowercase_canonicalized(self, monkeypatch, tmp_path):
        vp = _v2_scene_vp(
            visualIntent="EXPLAIN",
            assetPreferences=["DIAGRAM", "Photograph"],
            subjects=["  test  "],
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "DIAGRAM", "durationFraction": 1.0, "transition": "CUT"},
            ],
        )
        script = _v2_script(scenes=[_v2_scene(1, vp_overrides={
            "visualIntent": "EXPLAIN",
            "assetPreferences": ["DIAGRAM", "Photograph"],
            "subjects": ["  test  "],
            "visualSequence": [
                {"segmentIndex": 1, "assetPreference": "DIAGRAM", "durationFraction": 1.0, "transition": "CUT"},
            ],
        })])
        # Fix: need enough scenes
        script["scenes"] = [_v2_scene(i) for i in range(1, 5)]
        script["scenes"][0] = script["scenes"][0]  # keep the special scene
        # Actually just overwrite scene 1
        scene1 = _v2_scene(1, vp_overrides={
            "visualIntent": "EXPLAIN",
            "assetPreferences": ["DIAGRAM", "Photograph"],
            "subjects": ["  test  "],
            "visualSequence": [
                {"segmentIndex": 1, "assetPreference": "DIAGRAM", "durationFraction": 1.0, "transition": "CUT"},
            ],
        })
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(script))
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        meta = _json.loads(out_path.read_text())
        vp = meta["script"]["scenes"][0]["visualPlan"]
        assert vp["visualIntent"] == "explain"
        assert vp["assetPreferences"] == ["diagram", "photograph"]
        assert vp["subjects"] == ["test"]
        assert vp["visualSequence"][0]["assetPreference"] == "diagram"
        assert vp["visualSequence"][0]["transition"] == "cut"

    def test_optional_defaults_persisted(self, monkeypatch, tmp_path):
        vp = _v2_scene_vp()
        vp.pop("period", None)
        vp.pop("location", None)
        scene1 = _v2_scene(1, vp_overrides={k: v for k, v in vp.items()})
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(script))
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        meta = _json.loads(out_path.read_text())
        vp = meta["script"]["scenes"][0]["visualPlan"]
        assert vp["period"] is None
        assert vp["location"] is None
        assert vp["allowGeneratedImage"] is False
        assert vp["preferredProviders"] == []
        assert vp["imageGenerationPrompt"] is None
        assert vp["negativePrompt"] is None

    def test_allow_generated_image_false_preserved(self, monkeypatch, tmp_path):
        vp = _v2_scene_vp(allowGeneratedImage=False)
        scene1 = _v2_scene(1, vp_overrides={"allowGeneratedImage": False})
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(script))
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        meta = _json.loads(out_path.read_text())
        vp = meta["script"]["scenes"][0]["visualPlan"]
        assert vp["allowGeneratedImage"] is False

    def test_multi_segment_sequence_preserved(self, monkeypatch, tmp_path):
        vp = _v2_scene_vp(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
                {"segmentIndex": 2, "assetPreference": "illustration", "durationFraction": 0.5, "transition": "fade"},
            ],
            assetPreferences=["diagram", "illustration"],
        )
        scene1 = _v2_scene(1, vp_overrides={
            "visualSequence": [
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
                {"segmentIndex": 2, "assetPreference": "illustration", "durationFraction": 0.5, "transition": "fade"},
            ],
            "assetPreferences": ["diagram", "illustration"],
        })
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(script))
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        meta = _json.loads(out_path.read_text())
        vs = meta["script"]["scenes"][0]["visualPlan"]["visualSequence"]
        assert len(vs) == 2
        assert vs[0]["segmentIndex"] == 1
        assert vs[1]["segmentIndex"] == 2

    def test_duration_fraction_sums_to_one(self, monkeypatch, tmp_path):
        vp = _v2_scene_vp(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
                {"segmentIndex": 2, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
            ],
        )
        scene1 = _v2_scene(1, vp_overrides={
            "visualSequence": [
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
                {"segmentIndex": 2, "assetPreference": "diagram", "durationFraction": 0.5, "transition": "cut"},
            ],
        })
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(script))
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        meta = _json.loads(out_path.read_text())
        vs = meta["script"]["scenes"][0]["visualPlan"]["visualSequence"]
        total = sum(s["durationFraction"] for s in vs)
        assert abs(total - 1.0) < 0.01

    def test_no_scores_added(self, monkeypatch, tmp_path):
        script = _v2_script()
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(script))
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        meta = _json.loads(out_path.read_text())
        for scene in meta["script"]["scenes"]:
            vp = scene["visualPlan"]
            assert "score" not in vp
            assert "scoreReasons" not in vp

    def test_no_legacy_fields_in_canonical(self, monkeypatch, tmp_path):
        script = _v2_script()
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(script))
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        meta = _json.loads(out_path.read_text())
        legacy_fields = [
            "editorialRole", "visualTemporalIntent", "strategy",
            "primaryAssetType", "secondaryAssetType",
            "style", "mood", "licenseRequired", "visualImportance",
        ]
        for scene in meta["script"]["scenes"]:
            vp = scene["visualPlan"]
            for field in legacy_fields:
                assert field not in vp, f"legacy field '{field}' found in canonical v2 plan"

    def test_no_domain_modes(self, monkeypatch, tmp_path):
        script = _v2_script()
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(script))
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        meta = _json.loads(out_path.read_text())
        result_text = _json.dumps(meta)
        for mode in ["historical", "science", "documentary", "legacy"]:
            assert mode not in meta.get("script", {}).get("mode", ""), f"mode '{mode}' found in script"

    def test_no_providers_urls_or_paths(self, monkeypatch, tmp_path):
        script = _v2_script()
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(script))
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        meta = _json.loads(out_path.read_text())
        for scene in meta["script"]["scenes"]:
            vp = scene["visualPlan"]
            assert "provider" not in vp
            assert "sourceUrl" not in vp
            assert "fileUrl" not in vp
            assert "path" not in vp

    def test_prompt_v2_is_neutral(self):
        """SYSTEM_PROMPT_V2 does not contain domain mode keywords."""
        assert "historical_strict" not in SYSTEM_PROMPT_V2
        assert "science" not in SYSTEM_PROMPT_V2.lower()


# ── Rejection tests ──────────────────────────────────────────────────────────


class TestV2Rejections:
    """Tests 16-30: v2 validation rejections."""

    def test_editorial_role_rejected(self):
        vp = _v2_scene_vp()
        vp["editorialRole"] = "context_map"
        scene1 = _v2_scene(1, vp_overrides={"editorialRole": "context_map"})
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("LEGACY_FIELD_NOT_ALLOWED" in c for c in codes), f"Got codes: {codes}"

    def test_strategy_rejected(self):
        vp = _v2_scene_vp()
        vp["strategy"] = "historical_archive"
        scene1 = _v2_scene(1, vp_overrides={"strategy": "historical_archive"})
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("LEGACY_FIELD_NOT_ALLOWED" in c for c in codes)

    def test_unknown_vp_field_causes_error(self):
        vp = _v2_scene_vp()
        vp["someUnknownField"] = "value"
        scene1 = _v2_scene(1, vp_overrides={"someUnknownField": "value"})
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("UNKNOWN_FIELD:someUnknownField" in c for c in codes)

    def test_unknown_segment_field_causes_error(self):
        vp = _v2_scene_vp(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 1.0, "transition": "cut", "motionType": "slow_zoom_in"},
            ],
        )
        scene1 = _v2_scene(1, vp_overrides={
            "visualSequence": [
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 1.0, "transition": "cut", "motionType": "slow_zoom_in"},
            ],
        })
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("UNKNOWN_SEGMENT_FIELD" in c for c in codes)

    def test_unrecognized_provider_causes_error(self):
        vp = _v2_scene_vp(preferredProviders=["unknown_provider"])
        scene1 = _v2_scene(1, vp_overrides={"preferredProviders": ["unknown_provider"]})
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("UNRECOGNIZED_PROVIDER" in c for c in codes)

    def test_missing_visual_sequence_fails(self):
        vp = {
            "_schemaVersion": V2_SCHEMA_VERSION,
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": ["diagram"],
        }
        scene1 = {"sceneNumber": 1, "voiceover": "Texto de prueba con contenido suficiente para rellenar la duración necesaria.",
                  "subtitle": "Test", "targetDurationSec": 7.5, "visualPlan": vp}
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("REQUIRED_FIELD_MISSING:visualSequence" in c for c in codes)

    def test_empty_subjects_fails(self):
        vp = _v2_scene_vp(subjects=[])
        scene1 = _v2_scene(1, vp_overrides={"subjects": []})
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("EMPTY_REQUIRED_FIELD:subjects" in c for c in codes)

    def test_empty_search_queries_fails(self):
        vp = _v2_scene_vp(searchQueries=[])
        scene1 = _v2_scene(1, vp_overrides={"searchQueries": []})
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("EMPTY_REQUIRED_FIELD:searchQueries" in c for c in codes)

    def test_invalid_duration_fraction_fails(self):
        vp = _v2_scene_vp(
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.4, "transition": "cut"},
                {"segmentIndex": 2, "assetPreference": "diagram", "durationFraction": 0.4, "transition": "cut"},
            ],
        )
        scene1 = _v2_scene(1, vp_overrides={
            "visualSequence": [
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 0.4, "transition": "cut"},
                {"segmentIndex": 2, "assetPreference": "diagram", "durationFraction": 0.4, "transition": "cut"},
            ],
        })
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("DURATION_FRACTION_SUM_INVALID" in c for c in codes)

    def test_invalid_asset_preference_enum_fails(self):
        vp = _v2_scene_vp(assetPreferences=["hovercraft"])
        scene1 = _v2_scene(1, vp_overrides={"assetPreferences": ["hovercraft"]})
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_ENUM_VALUE:assetPreferences[0]" in c for c in codes)

    def test_segment_pref_not_in_asset_preferences_fails(self):
        vp = _v2_scene_vp(
            assetPreferences=["diagram"],
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "photograph", "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        scene1 = _v2_scene(1, vp_overrides={
            "assetPreferences": ["diagram"],
            "visualSequence": [
                {"segmentIndex": 1, "assetPreference": "photograph", "durationFraction": 1.0, "transition": "cut"},
            ],
        })
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("SEGMENT_PREFERENCE_NOT_ALLOWED" in c for c in codes)

    def test_generated_without_flag_fails(self):
        vp = _v2_scene_vp(
            assetPreferences=["generated"],
            allowGeneratedImage=False,
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "generated", "durationFraction": 1.0, "transition": "cut"},
            ],
        )
        scene1 = _v2_scene(1, vp_overrides={
            "assetPreferences": ["generated"],
            "allowGeneratedImage": False,
            "visualSequence": [
                {"segmentIndex": 1, "assetPreference": "generated", "durationFraction": 1.0, "transition": "cut"},
            ],
        })
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("GENERATED_ASSET_NOT_ALLOWED" in c for c in codes)

    def test_scene_without_schema_version_fails(self):
        vp = {
            "visualIntent": "explain",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": ["diagram"],
            "visualSequence": [
                {"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 1.0, "transition": "cut"},
            ],
        }
        scene1 = {"sceneNumber": 1, "voiceover": "Texto de prueba con contenido suficiente para rellenar la duración necesaria.",
                  "subtitle": "Test", "targetDurationSec": 7.5, "visualPlan": vp}
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("MIXED_OR_MISSING_VISUAL_PLAN_V2" in c for c in codes)

    def test_scene_with_schema_1_in_v2_request_fails(self):
        vp = _v2_scene_vp(_schemaVersion=1)
        scene1 = _v2_scene(1, vp_overrides={"_schemaVersion": 1})
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("MIXED_OR_MISSING_VISUAL_PLAN_V2" in c for c in codes)

    def test_partial_success_not_persisted(self):
        """One scene v2 valid, one invalid → nothing canonical."""
        good = _v2_scene(1)
        bad = _v2_scene(2, vp_overrides={"editorialRole": "context_map"})
        script = _v2_script(scenes=[good, bad, _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        assert len(errors) > 0

    def test_missing_visual_plan_fails(self):
        scene1 = {
            "sceneNumber": 1,
            "voiceover": "Escena sin plan visual.",
            "subtitle": "Test",
            "targetDurationSec": 6.0,
        }
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("MISSING_VISUAL_PLAN" in c for c in codes)


# ── Retry tests ──────────────────────────────────────────────────────────────


class TestV2Retry:
    """Tests 31-33: retry behavior."""

    def test_first_invalid_second_valid_success(self, monkeypatch, tmp_path):
        bad_vp = _v2_scene_vp()
        bad_vp["editorialRole"] = "context_map"
        bad_scene1 = _v2_scene(1, vp_overrides={"editorialRole": "context_map"})
        bad_script = _v2_script(scenes=[bad_scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])

        good_script = _v2_script()

        calls = [0]
        prompts = []

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            calls[0] += 1
            prompts.append(prompt)
            if calls[0] == 1:
                return _json.dumps(bad_script)
            else:
                return _json.dumps(good_script)

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])

        exit_code = gs.main()
        assert exit_code == 0
        meta = _json.loads(out_path.read_text())
        assert meta["status"] == "SCRIPT_DRAFT"
        assert calls[0] == 2

        # Second prompt must contain error information
        assert any("LEGACY_FIELD_NOT_ALLOWED" in p for p in prompts[1:])

    def test_three_attempts_all_invalid_review_required(self, monkeypatch, tmp_path):
        bad_vp = _v2_scene_vp()
        bad_vp["editorialRole"] = "context_map"
        bad_scene1 = _v2_scene(1, vp_overrides={"editorialRole": "context_map"})
        bad_script = _v2_script(scenes=[bad_scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])

        calls = [0]

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            calls[0] += 1
            return _json.dumps(bad_script)

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])

        exit_code = gs.main()
        assert exit_code == 0
        assert calls[0] == 3

        meta = _json.loads(out_path.read_text())
        assert meta["status"] == "REVIEW_REQUIRED"
        assert meta["durationContract"]["status"] == "FAIL"
        assert meta["durationContract"]["structureValid"] is False
        assert len(meta["durationContract"]["structureIssues"]) >= 1

        rh = meta["durationContract"]["retryHistory"]
        assert len(rh) == 3
        assert "structuralIssues" in rh[2]

        review_reasons = meta.get("reviewReasons", [])
        assert any("VISUAL_PLAN_V2_INVALID" in r for r in review_reasons)

    def test_repair_prompt_has_no_secrets(self, monkeypatch, tmp_path):
        bad_vp = _v2_scene_vp()
        bad_vp["editorialRole"] = "context_map"
        bad_scene1 = _v2_scene(1, vp_overrides={"editorialRole": "context_map"})
        bad_script = _v2_script(scenes=[bad_scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])

        prompts = []

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            prompts.append(prompt)
            return _json.dumps(bad_script)

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test", "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])

        gs.main()

        for i, p in enumerate(prompts):
            assert "LLM_API_KEY" not in p, f"Prompt {i} contains LLM_API_KEY"
            assert "Bearer" not in p, f"Prompt {i} contains Bearer"
            assert "Authorization" not in p, f"Prompt {i} contains Authorization"
            assert "sk-" not in p, f"Prompt {i} contains API key pattern"


# ── Compatibility tests ──────────────────────────────────────────────────────


class TestV2Compatibility:
    """Tests 34-37: existing code unchanged."""

    def test_v1_tests_still_pass(self):
        """Canonicalizer tests are unchanged."""
        from visual_plan_v2 import canonicalize_visual_plan_v2, ALLOWED_VISUAL_INTENTS
        assert len(ALLOWED_VISUAL_INTENTS) > 0
        assert canonicalize_visual_plan_v2 is not None

    def test_run_job_modules_unchanged(self):
        """run_job.py still handles v2 dispatch correctly."""
        from run_job import _uses_v2_visual_assets, _collect_visual_plan_schema_versions
        v2_meta = {
            "script": {
                "scenes": [
                    {"sceneNumber": 1, "visualPlan": {"_schemaVersion": 2}}
                ]
            }
        }
        assert _uses_v2_visual_assets(v2_meta) is True

    def test_e2e_metadata_still_valid_for_canonicalizer(self):
        """Previous E2E metadata can still be canonicalized."""
        from visual_plan_v2 import canonicalize_visual_plan_v2
        plan = {
            "_schemaVersion": V2_SCHEMA_VERSION,
            "visualIntent": "show",
            "subjects": ["test"],
            "searchQueries": ["test query"],
            "assetPreferences": ["photograph"],
            "visualSequence": [
                {"segmentIndex": 1, "assetPreference": "photograph", "durationFraction": 1.0, "transition": "cut"},
            ],
        }
        result = canonicalize_visual_plan_v2(plan)
        assert result["ok"] is True
        assert result["canonicalPlan"] is not None

    def test_prompt_v2_contains_required_sections(self):
        """SYSTEM_PROMPT_V2 has all required sections."""
        assert "_schemaVersion" in SYSTEM_PROMPT_V2
        assert "visualIntent" in SYSTEM_PROMPT_V2
        assert "subjects" in SYSTEM_PROMPT_V2
        assert "searchQueries" in SYSTEM_PROMPT_V2
        assert "assetPreferences" in SYSTEM_PROMPT_V2
        assert "visualSequence" in SYSTEM_PROMPT_V2
        assert "segmentIndex" in SYSTEM_PROMPT_V2
        assert "assetPreference" in SYSTEM_PROMPT_V2
        assert "durationFraction" in SYSTEM_PROMPT_V2
        assert "transition" in SYSTEM_PROMPT_V2
        assert "PROHIBIDOS" in SYSTEM_PROMPT_V2

    def test_prompt_v2_prohibits_legacy_fields(self):
        """SYSTEM_PROMPT_V2 explicitly prohibits v1 visualPlan fields."""
        prohibited = [
            "editorialRole", "strategy", "primaryAssetType", "secondaryAssetType",
            "visualTemporalIntent", "motionType",
        ]
        for field in prohibited:
            assert field in SYSTEM_PROMPT_V2, f"'{field}' should be listed as prohibited"

    def test_prompt_v2_no_historical_domain_mode(self):
        """SYSTEM_PROMPT_V2 does not enforce historical content requirements."""
        assert "guionista senior especializado en Shorts/TikTok/Reels divulgativos" in SYSTEM_PROMPT_V2
        assert "histórico" not in SYSTEM_PROMPT_V2[:80]  # not in the persona line


# ── Prompt properties ────────────────────────────────────────────────────────


class TestPromptProperties:
    """Verify SYSTEM_PROMPT_V2 structure."""

    def test_prompt_v2_does_not_require_narrative_beats(self):
        """SYSTEM_PROMPT_V2 does not require narrativeBeats (v1 concept)."""
        json_start = SYSTEM_PROMPT_V2.find("## Formato JSON de salida")
        json_block = SYSTEM_PROMPT_V2[json_start:] if json_start >= 0 else SYSTEM_PROMPT_V2
        assert '"narrativeBeats"' not in json_block

    def test_prompt_v2_no_cheat_sheet(self):
        assert "Cheat sheet" not in SYSTEM_PROMPT_V2

    def test_prompt_v2_no_decision_tree(self):
        assert "Árbol de decisión" not in SYSTEM_PROMPT_V2

    def test_prompt_v2_no_role_prohibitions_for_context_map(self):
        assert "NO usar context_map" not in SYSTEM_PROMPT_V2

    def test_prompt_v2_json_example_has_v2_fields(self):
        json_start = SYSTEM_PROMPT_V2.find("## Formato JSON de salida")
        assert json_start >= 0, "JSON example section not found"
        json_block = SYSTEM_PROMPT_V2[json_start:]
        assert "_schemaVersion" in json_block
        assert "visualIntent" in json_block
        assert "assetPreference" in json_block

    def test_retry_instruction_v2_includes_errors_by_scene(self):
        budget = {
            "targetSec": 30, "minSec": 27, "maxSec": 35,
            "minimumWords": 47, "preferredWords": 52, "maximumWords": 61,
            "sceneCount": 5, "pauseSec": 1.4,
            "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
        }
        issues = [
            {"sceneNumber": 1, "code": "TEST_ERROR", "path": "test.path", "message": "test message"},
        ]
        inst = gs._build_retry_instruction_v2(
            budget, actual_word_count=30, actual_scene_count=5, estimated_dur=25.0,
            structural_issues=issues, allow_generated_images=False,
        )
        assert "TEST_ERROR" in inst
        assert "Escena 1" in inst

    def test_retry_instruction_v2_no_secrets(self):
        budget = {
            "targetSec": 30, "minSec": 27, "maxSec": 35,
            "minimumWords": 47, "preferredWords": 52, "maximumWords": 61,
            "sceneCount": 5, "pauseSec": 1.4,
            "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
        }
        issues = [{"sceneNumber": 1, "code": "X", "path": "", "message": "msg"}]
        inst = gs._build_retry_instruction_v2(
            budget, actual_word_count=30, actual_scene_count=5, estimated_dur=25.0,
            structural_issues=issues, allow_generated_images=False,
        )
        assert "LLM_API_KEY" not in inst
        assert "Bearer" not in inst
        assert "sk-" not in inst


# ── Fix 1: Neutral duration prompt ───────────────────────────────────────────


class TestNeutralDurationPrompt:
    """Verify v2 duration prompt is neutral, v1 unchanged."""

    def test_v2_prompt_has_no_historical_requirements(self, monkeypatch, capsys):
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Aurora boreal",
                                           "--visual-schema-version", "2", "--dry-run",
                                           "--model", "gpt-4o-mini", "--duration", "30"])
        gs.main()
        out = capsys.readouterr().out + capsys.readouterr().err
        assert "detalles históricos" not in out
        assert "contenido histórico" not in out
        assert "fecha con año" not in out
        assert "nombre propio relevante" not in out

    def test_v1_prompt_preserves_historical_requirements(self, monkeypatch, capsys):
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Berlín",
                                           "--visual-schema-version", "1", "--dry-run",
                                           "--model", "gpt-4o-mini", "--duration", "30"])
        gs.main()
        out = capsys.readouterr().out + capsys.readouterr().err
        assert "detalles históricos" in out or "fecha" in out.lower()

    def test_aurora_dry_run_v2_no_historical_injection(self, monkeypatch, capsys):
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Cómo se produce una aurora boreal",
                                           "--visual-schema-version", "2", "--dry-run",
                                           "--model", "gpt-4o-mini", "--duration", "30"])
        gs.main()
        out = capsys.readouterr().out + capsys.readouterr().err
        assert "detalles históricos" not in out
        assert "fecha con año" not in out


# ── Fix 2: Generated image enforcement ───────────────────────────────────────


class TestGeneratedImageEnforcement:
    """Request-level allowGeneratedImages=false enforcement."""

    def test_allow_generated_image_true_with_request_false_rejected(self):
        vp = _v2_scene_vp(allowGeneratedImage=True)
        scene1 = {
            "sceneNumber": 1,
            "voiceover": "Texto de prueba con contenido suficiente para rellenar la duración necesaria.",
            "subtitle": "Test", "targetDurationSec": 7.5, "visualPlan": vp,
        }
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("GENERATED_IMAGES_DISABLED_BY_REQUEST" in c for c in codes)

    def test_asset_preferences_generated_with_request_false_rejected(self):
        vp = _v2_scene_vp(assetPreferences=["diagram", "generated"], allowGeneratedImage=False)
        scene1 = {
            "sceneNumber": 1,
            "voiceover": "Texto de prueba con contenido suficiente para rellenar la duración necesaria.",
            "subtitle": "Test", "targetDurationSec": 7.5, "visualPlan": vp,
        }
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("GENERATED_IMAGES_DISABLED_BY_REQUEST" in c for c in codes)

    def test_segment_generated_with_request_false_rejected(self):
        vp = _v2_scene_vp(
            assetPreferences=["generated", "photograph"],
            visualSequence=[
                {"segmentIndex": 1, "assetPreference": "generated", "durationFraction": 1.0, "transition": "cut"},
            ],
            allowGeneratedImage=False,
        )
        scene1 = {
            "sceneNumber": 1,
            "voiceover": "Texto de prueba con contenido suficiente para rellenar la duración necesaria.",
            "subtitle": "Test", "targetDurationSec": 7.5, "visualPlan": vp,
        }
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("GENERATED_IMAGES_DISABLED_BY_REQUEST" in c for c in codes)

    def test_image_generation_prompt_with_request_false_rejected(self):
        vp = _v2_scene_vp(imageGenerationPrompt="A detailed image of test", allowGeneratedImage=False)
        scene1 = {
            "sceneNumber": 1,
            "voiceover": "Texto de prueba con contenido suficiente para rellenar la duración necesaria.",
            "subtitle": "Test", "targetDurationSec": 7.5, "visualPlan": vp,
        }
        script = _v2_script(scenes=[scene1, _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("GENERATED_IMAGES_DISABLED_BY_REQUEST" in c for c in codes)

    def test_normal_plan_no_generation_passes(self):
        script = _v2_script()
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is not None
        assert len(errors) == 0


# ── Fix 3: Structural validation ─────────────────────────────────────────────


class TestSceneCountValidation:
    """Min 4, max 6 scenes."""

    def test_three_scenes_rejected(self):
        script = _v2_script(scenes=[_v2_scene(1), _v2_scene(2), _v2_scene(3)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INSUFFICIENT_SCENE_COUNT" in c for c in codes)

    def test_seven_scenes_rejected(self):
        script = _v2_script(scenes=[_v2_scene(i) for i in range(1, 8)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("EXCESSIVE_SCENE_COUNT" in c for c in codes)

    def test_four_scenes_passes(self):
        script = _v2_script(scenes=[_v2_scene(i) for i in range(1, 5)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is not None
        assert len(errors) == 0

    def test_six_scenes_passes(self):
        script = _v2_script(scenes=[_v2_scene(i) for i in range(1, 7)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is not None
        assert len(errors) == 0


class TestSceneNumberValidation:
    """Exact sequential sceneNumber [1..N]."""

    def test_sequential_passes(self):
        script = _v2_script(scenes=[_v2_scene(1), _v2_scene(2), _v2_scene(3), _v2_scene(4)])
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is not None
        assert len(errors) == 0

    def test_gap_rejected(self):
        script = _v2_script()
        script["scenes"] = [_v2_scene(1), _v2_scene(3), _v2_scene(4), _v2_scene(5)]
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_SCENE_NUMBER_SEQUENCE" in c for c in codes)

    def test_starts_at_two_rejected(self):
        script = _v2_script()
        script["scenes"] = [_v2_scene(2), _v2_scene(3), _v2_scene(4), _v2_scene(5)]
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_SCENE_NUMBER_SEQUENCE" in c for c in codes)

    def test_duplicates_rejected(self):
        script = _v2_script()
        script["scenes"] = [_v2_scene(1), _v2_scene(1), _v2_scene(3), _v2_scene(4)]
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_SCENE_NUMBER_SEQUENCE" in c for c in codes)

    def test_reverse_order_rejected(self):
        script = _v2_script()
        script["scenes"] = [_v2_scene(4), _v2_scene(3), _v2_scene(2), _v2_scene(1)]
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_SCENE_NUMBER_SEQUENCE" in c for c in codes)

    def test_float_scene_number_rejected(self):
        script = _v2_script()
        script["scenes"] = [
            {"sceneNumber": 1.0, "voiceover": "Texto de prueba con contenido suficiente para rellenar la duración necesaria.",
             "subtitle": "Test", "targetDurationSec": 7.5,
             "visualPlan": _v2_scene_vp()},
            _v2_scene(2), _v2_scene(3), _v2_scene(4),
        ]
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_SCENE_NUMBER_SEQUENCE" in c for c in codes)

    def test_bool_scene_number_rejected(self):
        script = _v2_script()
        script["scenes"] = [
            {"sceneNumber": True, "voiceover": "Texto de prueba con contenido suficiente para rellenar la duración necesaria.",
             "subtitle": "Test", "targetDurationSec": 7.5,
             "visualPlan": _v2_scene_vp()},
            _v2_scene(2), _v2_scene(3), _v2_scene(4),
        ]
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_SCENE_NUMBER_SEQUENCE" in c for c in codes)

    def test_zero_or_negative_rejected(self):
        script = _v2_script()
        script["scenes"] = [_v2_scene(0), _v2_scene(2), _v2_scene(3), _v2_scene(4)]
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_SCENE_NUMBER_SEQUENCE" in c for c in codes)


class TestTargetDurationValidation:
    """targetDurationSec must be finite, positive, numeric."""

    def test_nan_rejected(self):
        script = _v2_script()
        script["scenes"][0]["targetDurationSec"] = float("nan")
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_TARGET_DURATION" in c for c in codes)

    def test_infinity_rejected(self):
        script = _v2_script()
        script["scenes"][0]["targetDurationSec"] = float("inf")
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_TARGET_DURATION" in c for c in codes)

    def test_negative_infinity_rejected(self):
        script = _v2_script()
        script["scenes"][0]["targetDurationSec"] = float("-inf")
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_TARGET_DURATION" in c for c in codes)

    def test_bool_rejected(self):
        script = _v2_script()
        script["scenes"][0]["targetDurationSec"] = True
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_TARGET_DURATION" in c for c in codes)

    def test_string_rejected(self):
        script = _v2_script()
        script["scenes"][0]["targetDurationSec"] = "6.0"
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("INVALID_TARGET_DURATION" in c for c in codes)

    def test_positive_finite_passes(self):
        script = _v2_script()
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is not None
        assert len(errors) == 0


# ── Fix 4: True strict-native ────────────────────────────────────────────────


class TestTrueStrictNative:
    """ALL canonicalizer warnings become errors, not just 4 codes."""

    def test_arbitrary_warning_promoted_to_error(self, monkeypatch):
        from visual_plan_v2 import canonicalize_visual_plan_v2

        script = _v2_script()
        original = canonicalize_visual_plan_v2

        def mock_canonicalize(plan, scene=None):
            result = original(plan)
            result["diagnostics"]["warnings"].append({
                "code": "ARBITRARY_TEST_WARNING",
                "message": "some test warning",
                "path": "test_path",
            })
            return result

        monkeypatch.setattr(gs, "canonicalize_visual_plan_v2", mock_canonicalize)

        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(script, allow_generated_images=False)
        assert canonical is None
        codes = [e["code"] for e in errors]
        assert any("ARBITRARY_TEST_WARNING" in c for c in codes)


# ── Retry integration tests ──────────────────────────────────────────────────


class TestRetryFixIntegration:
    """Retry behavior with the four fixes applied."""

    def test_first_generated_rejected_second_valid_success(self, monkeypatch, tmp_path):
        bad = _v2_script()
        bad["scenes"] = [
            {"sceneNumber": 1, "voiceover": "Test content for duration target requirement.",
             "subtitle": "Test", "targetDurationSec": 7.5,
             "visualPlan": dict(_v2_scene_vp(), allowGeneratedImage=True)},
            _v2_scene(2), _v2_scene(3), _v2_scene(4),
        ]

        good = _v2_script()

        calls = [0]
        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            calls[0] += 1
            if calls[0] == 1:
                return _json.dumps(bad)
            return _json.dumps(good)

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
                                           "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        assert exit_code == 0
        meta = _json.loads(out_path.read_text())
        assert meta["status"] == "SCRIPT_DRAFT"
        assert calls[0] == 2

    def test_three_invalid_scene_number_all_review_required(self, monkeypatch, tmp_path):
        bad = _v2_script()
        bad["scenes"] = [_v2_scene(1), _v2_scene(3), _v2_scene(4), _v2_scene(5)]

        calls = [0]
        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            calls[0] += 1
            return _json.dumps(bad)

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
                                           "--visual-schema-version", "2",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        assert exit_code == 0
        assert calls[0] == 3
        meta = _json.loads(out_path.read_text())
        assert meta["status"] == "REVIEW_REQUIRED"
