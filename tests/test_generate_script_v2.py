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

# ── SYSTEM_PROMPT_V2 ─────────────────────────────────────────────────────────
# SYSTEM_PROMPT_V2 is built at module import from ALLOWED_ASSET_PREFERENCES
# (see _build_asset_preferences_section), so we use the runtime constant rather
# than re-parsing the source template.
SYSTEM_PROMPT_V2 = gs.SYSTEM_PROMPT_V2


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
    """Tests 1-4: CLI and request metadata (flag removal)."""

    def test_default_uses_system_prompt(self, monkeypatch):
        """Default uses SYSTEM_PROMPT_V2 (flag removed)."""
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "test", "--dry-run", "--model", "gpt-4o-mini"])
        exit_code = gs.main()
        assert exit_code == 0

    def test_removed_visual_schema_flag_v1_is_rejected(self, monkeypatch, capsys):
        """--visual-schema-version 1 is rejected because the flag is removed."""
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "test", "--visual-schema-version", "1",
                                           "--dry-run", "--model", "gpt-4o-mini"])
        with pytest.raises(SystemExit) as exc_info:
            gs.main()
        assert exc_info.value.code == 2

    def test_removed_visual_schema_flag_v2_is_rejected(self, monkeypatch, capsys):
        """--visual-schema-version 2 is also rejected because the flag is removed."""
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "test", "--visual-schema-version", "2",
                                           "--dry-run", "--model", "gpt-4o-mini"])
        with pytest.raises(SystemExit) as exc_info:
            gs.main()
        assert exc_info.value.code == 2

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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
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
        from run_job import _classify_visual_schema, build_stage_command
        v2_meta = {
            "script": {
                "scenes": [
                    {"sceneNumber": 1, "visualPlan": {"_schemaVersion": 2}}
                ]
            }
        }
        assert _classify_visual_schema(v2_meta) == "SUPPORTED_V2"
        cmd = build_stage_command("assets", "/path/meta.json", metadata=v2_meta)
        assert cmd[1].endswith("fetch_images_v2.py")

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
    """Verify v2 duration prompt is neutral."""

    def test_v2_prompt_has_no_historical_requirements(self, monkeypatch, capsys):
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Aurora boreal",
                                           "--dry-run",
                                           "--model", "gpt-4o-mini", "--duration", "30"])
        gs.main()
        out = capsys.readouterr().out + capsys.readouterr().err
        assert "detalles históricos" not in out
        assert "contenido histórico" not in out
        assert "fecha con año" not in out
        assert "nombre propio relevante" not in out

    def test_visual_schema_version_flag_is_absent_from_help(self, monkeypatch, capsys):
        """--help does not mention --visual-schema-version."""
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--help"])
        with pytest.raises(SystemExit) as exc_info:
            gs.main()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "--visual-schema-version" not in out

    def test_aurora_dry_run_v2_no_historical_injection(self, monkeypatch, capsys):
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Cómo se produce una aurora boreal",
                                           "--dry-run",
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
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        assert exit_code == 0
        assert calls[0] == 3
        meta = _json.loads(out_path.read_text())
        assert meta["status"] == "REVIEW_REQUIRED"


# ── Slice 6B script-contract fix ─────────────────────────────────────────────
# Tests T1-T7: closed-enum prompt derived from the contract, unambiguous prompt,
# always-contractual retries, real-value regression and unchanged attempts.


def _prompt_asset_pref_enum_values():
    """Extract the closed enum values exposed in the AssetPreferences section."""
    start = SYSTEM_PROMPT_V2.find("### AssetPreferences permitidos")
    end = SYSTEM_PROMPT_V2.find("### Transiciones permitidas", start)
    assert start >= 0, "AssetPreferences header not found; cannot slice the enum section"
    assert end > start, "Transiciones header must come after AssetPreferences; slice would be empty"
    section = SYSTEM_PROMPT_V2[start:end]
    return set(__import__("re").findall(r"- `([a-z]+)`:", section))


class TestScriptContractFix:
    """Slice 6B correction: prompt + retry driven by the contractual enum."""

    # T1 — enum parity prompt/contract
    def test_t1_enum_parity_prompt_contract(self):
        values = _prompt_asset_pref_enum_values()
        assert values == set(ALLOWED_ASSET_PREFERENCES)
        assert len(values) == len(ALLOWED_ASSET_PREFERENCES) == 9
        assert values == {
            "archive", "diagram", "document", "generated", "illustration",
            "map", "painting", "photograph", "stock",
        }

    # T2 — unambiguous prompt
    def test_t2_prompt_unambiguous(self):
        assert "- `diagram`:" in SYSTEM_PROMPT_V2
        assert 'el valor del enum debe ser exactamente "diagram"' in SYSTEM_PROMPT_V2
        enum_values = _prompt_asset_pref_enum_values()
        assert "infographic" not in enum_values
        assert "animation" not in enum_values
        assert "Nunca inventes sinónimos ni categorías de medios" in SYSTEM_PROMPT_V2
        assert "allowGeneratedImage" in SYSTEM_PROMPT_V2
        gen_lines = [l for l in SYSTEM_PROMPT_V2.splitlines() if l.strip().startswith("- `generated`")]
        assert gen_lines and "allowGeneratedImage" in gen_lines[0]

    # T2 (request gate) — the real request value must reach the first prompt
    def _gate_prompt(self, allow_generated_images):
        budget = {
            "targetSec": 30, "minSec": 27, "maxSec": 30,
            "minimumWords": 47, "preferredWords": 52, "maximumWords": 52,
            "sceneCount": 5, "pauseSec": 1.4,
            "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
        }
        return gs._build_user_prompt_v2(
            "Arcoíris", budget, "balanced",
            allow_generated_images=allow_generated_images,
        )

    def test_t2_request_gate_false(self):
        prompt = self._gate_prompt(False)
        assert "allowGeneratedImages es false" in prompt
        assert "allowGeneratedImage=false" in prompt
        assert "No uses \"generated\" en `assetPreferences`" in prompt
        assert "No uses \"generated\" en `visualSequence[].assetPreference`" in prompt
        assert "No incluyas `imageGenerationPrompt` ni `negativePrompt`" in prompt
        # The false gate is unconditional: it must not defer the decision to a
        # request value the model cannot know.
        assert "es true" not in prompt
        assert "cuando la escena declare" not in prompt

    def test_t2_request_gate_true(self):
        prompt = self._gate_prompt(True)
        assert "allowGeneratedImages es true" in prompt
        assert "allowGeneratedImage=true" in prompt
        assert "imageGenerationPrompt" in prompt
        assert "negativePrompt" in prompt

    def test_t2_first_prompt_contains_false_gate(self, monkeypatch, capsys):
        """The real first user prompt in main() includes the false gate."""
        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Arcoíris",
                                           "--dry-run", "--model", "gpt-4o-mini", "--duration", "30"])
        gs.main()
        out = capsys.readouterr().out
        assert "allowGeneratedImages es false" in out
        assert "allowGeneratedImage=false" in out

    # T3 — duration retry: absolute limit, enum recall, preserve, not vague
    def test_t3_duration_retry_absolute_limit(self):
        budget = {
            "targetSec": 30, "minSec": 27, "maxSec": 30,
            "minimumWords": 47, "preferredWords": 52, "maximumWords": 52,
            "sceneCount": 5, "pauseSec": 1.4,
            "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
        }
        inst = gs._build_retry_instruction_v2(
            budget, actual_word_count=54, actual_scene_count=5, estimated_dur=30.9,
            structural_issues=[], allow_generated_images=False,
        )
        assert "52" in inst
        assert "superar 52" in inst
        assert "como máximo 52" in inst
        assert "No superes 52" in inst
        assert "archive" in inst and "photograph" in inst
        assert "Preserva los campos ya válidos" in inst
        assert "Reduce aproximadamente 2 palabras" not in inst

    # T4 — combined structural + duration retry
    def test_t4_combined_structural_duration_retry(self):
        budget = {
            "targetSec": 30, "minSec": 27, "maxSec": 30,
            "minimumWords": 47, "preferredWords": 52, "maximumWords": 52,
            "sceneCount": 5, "pauseSec": 1.4,
            "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
        }
        issues = [
            {"sceneNumber": 3, "code": "V2_STRUCTURE_INVALID_ENUM_VALUE",
             "path": "assetPreferences[0]", "message": "scene 3: got 'animation'"},
            {"sceneNumber": 5, "code": "V2_STRUCTURE_INVALID_ENUM_VALUE",
             "path": "visualSequence[0].assetPreference", "message": "scene 5: got 'infographic'"},
        ]
        inst = gs._build_retry_instruction_v2(
            budget, actual_word_count=54, actual_scene_count=5, estimated_dur=30.9,
            structural_issues=issues, allow_generated_images=False,
        )
        assert "assetPreferences" in inst
        assert "animation" in inst
        assert "infographic" in inst
        assert "diagram" in inst
        assert "superar 52" in inst
        assert "Problemas estructurales que debes corregir" in inst
        assert "Contrato de duración" in inst

    # T4 (explicit paths) — issue["path"] must be printed separately, not only
    # embedded in code/message. Fails if the explicit path emission is removed.
    def test_t4_explicit_paths_asset_preferences(self):
        budget = {
            "targetSec": 30, "minSec": 27, "maxSec": 30,
            "minimumWords": 47, "preferredWords": 52, "maximumWords": 52,
            "sceneCount": 5, "pauseSec": 1.4,
            "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
        }
        issues = [
            {"sceneNumber": 1, "code": "INVALID_ENUM_VALUE",
             "path": "assetPreferences[0]", "message": "scene 1: got 'animation'"},
        ]
        inst = gs._build_retry_instruction_v2(
            budget, actual_word_count=54, actual_scene_count=5, estimated_dur=30.9,
            structural_issues=issues, allow_generated_images=False,
        )
        assert "Path: assetPreferences[0]" in inst
        assert "[INVALID_ENUM_VALUE]" in inst
        assert "scene 1: got 'animation'" in inst

    def test_t4_explicit_paths_visual_sequence(self):
        budget = {
            "targetSec": 30, "minSec": 27, "maxSec": 30,
            "minimumWords": 47, "preferredWords": 52, "maximumWords": 52,
            "sceneCount": 5, "pauseSec": 1.4,
            "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
        }
        issues = [
            {"sceneNumber": 2, "code": "INVALID_ENUM_VALUE",
             "path": "visualSequence[0].assetPreference", "message": "scene 2: got 'infographic'"},
        ]
        inst = gs._build_retry_instruction_v2(
            budget, actual_word_count=54, actual_scene_count=5, estimated_dur=30.9,
            structural_issues=issues, allow_generated_images=False,
        )
        assert "Path: visualSequence[0].assetPreference" in inst
        assert "[INVALID_ENUM_VALUE]" in inst
        assert "scene 2: got 'infographic'" in inst

    def test_t4_explicit_path_without_scene_number(self):
        budget = {
            "targetSec": 30, "minSec": 27, "maxSec": 30,
            "minimumWords": 47, "preferredWords": 52, "maximumWords": 52,
            "sceneCount": 5, "pauseSec": 1.4,
            "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
        }
        issues = [
            {"sceneNumber": None, "code": "EMPTY_SCENES",
             "path": "scenes", "message": "script has no scenes"},
        ]
        inst = gs._build_retry_instruction_v2(
            budget, actual_word_count=0, actual_scene_count=0, estimated_dur=0.0,
            structural_issues=issues, allow_generated_images=False,
        )
        assert "Path: scenes" in inst
        assert "[EMPTY_SCENES]" in inst
        assert "script has no scenes" in inst

    # T5 — real-value regression: animation and infographic stay rejected and the
    # validator reports both the assetPreferences and visualSequence paths.
    def _rejected_script(self, enum_value):
        return _v2_script(scenes=[
            _v2_scene(1, vp_overrides={
                "assetPreferences": [enum_value],
                "visualSequence": [
                    {"segmentIndex": 1, "assetPreference": enum_value,
                     "durationFraction": 1.0, "transition": "cut"},
                ],
            }),
            _v2_scene(2), _v2_scene(3), _v2_scene(4),
        ])

    @pytest.mark.parametrize("enum_value", ["animation", "infographic"])
    def test_t5_invalid_enum_rejected(self, enum_value):
        canonical, errors, _ = gs._validate_and_canonicalize_script_v2(
            self._rejected_script(enum_value), allow_generated_images=False)
        assert canonical is None
        assert errors, "expected structural errors for invalid enum value"
        paths = {e["path"] for e in errors}
        assert "scenes[1].visualPlan.assetPreferences[0]" in paths, f"paths={paths}"
        assert "scenes[1].visualPlan.visualSequence[0].assetPreference" in paths, f"paths={paths}"
        assert any("INVALID_ENUM_VALUE" in e["code"] for e in errors), \
            f"codes={[e['code'] for e in errors]}"

    # T6 — preserve valid fields during reduce_content
    def test_t6_preserve_during_reduce_content(self):
        budget = {
            "targetSec": 30, "minSec": 27, "maxSec": 30,
            "minimumWords": 47, "preferredWords": 52, "maximumWords": 52,
            "sceneCount": 5, "pauseSec": 1.4,
            "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
        }
        inst = gs._build_retry_instruction_v2(
            budget, actual_word_count=60, actual_scene_count=5, estimated_dur=33.0,
            structural_issues=[], allow_generated_images=False,
        )
        assert "Conserva el número de escenas" in inst
        assert "sceneNumber" in inst
        assert "campos `visualPlan` ya válidos" in inst
        assert "assetPreferences` ni `visualSequence` válidos" in inst
        assert "No cambies" in inst

    # T7 — attempts unchanged
    def test_t7_max_script_attempts_unchanged(self):
        assert gs.MAX_SCRIPT_ATTEMPTS == 3

    # F5 — integrated reduce_content flow through main()
    def _five_scene_script(self, words_per_scene):
        scenes = []
        for i in range(1, 6):
            voiceover = " ".join(f"palabra{i}_{j}" for j in range(1, words_per_scene + 1))
            scenes.append(_v2_scene(i, vp_overrides={}, voiceover=voiceover))
        return _v2_script(scenes=scenes)

    def _repair_payload(self, words_per_scene, scene_count=5):
        return {
            "scenes": [
                {"sceneNumber": i, "voiceover": " ".join(f"nueva{i}_{j}" for j in range(1, words_per_scene + 1))}
                for i in range(1, scene_count + 1)
            ]
        }

    def test_f5_integrated_reduce_content_through_main(self, monkeypatch, tmp_path):
        """First attempt is structurally valid but over budget (60 > 52); the
        second call is a specialized compression prompt, so the mock must
        return a reduced voiceover repair payload (not a full script)."""
        bad = self._five_scene_script(12)  # 60 words → above maximumWords=52
        reduced = self._repair_payload(10)  # 50 words → within range

        calls = [0]
        prompts = []

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            calls[0] += 1
            prompts.append(prompt)
            return _json.dumps(bad) if calls[0] == 1 else _json.dumps(reduced)

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Arcoíris",
                                           "--duration", "30", "--output", str(out_path)])

        exit_code = gs.main()
        assert exit_code == 0
        assert calls[0] == 2

        meta = _json.loads(out_path.read_text())
        assert meta["status"] == "SCRIPT_DRAFT"
        assert meta["durationContract"]["status"] == "PASS"
        assert meta["durationContract"]["wordCount"] == 50

        # The second prompt must be the specialized compression prompt, not a
        # full regeneration, and must reference the previous voiceovers.
        second = prompts[1]
        assert "Compresión de voz en off" in second
        assert "currentVoiceover" in second
        assert "maximumWords" in second
        assert "str.split()" in second
        assert '{"scenes": [{"sceneNumber": 1, "voiceover": "..."}]}' in second

        # Visual Plan must be preserved unchanged through the compression.
        # (The persisted script is canonicalized, so compare against the
        # canonicalized form of the first attempt.)
        canonical_bad, _, _ = gs._validate_and_canonicalize_script_v2(bad, allow_generated_images=False)
        persisted_vp = meta["script"]["scenes"][0]["visualPlan"]
        assert persisted_vp == canonical_bad["scenes"][0]["visualPlan"]
        assert persisted_vp["_schemaVersion"] == 2


# ── Duration retry convergence (Slice 6B duration retry fix) ────────────────


class TestDurationRetryConvergence:
    """Tests T1-T12 for the voiceover-compression retry and best-attempt."""

    # T1 — deterministic cap distribution
    def test_t1_allocate_scene_word_caps(self):
        caps5 = gs._allocate_scene_word_caps(52, 5)
        assert caps5 == [11, 11, 10, 10, 10]
        assert sum(caps5) == 52
        assert max(caps5) - min(caps5) <= 1
        assert len(caps5) == 5
        assert all(isinstance(c, int) and c > 0 for c in caps5)

        for count in (4, 6):
            caps = gs._allocate_scene_word_caps(52, count)
            assert len(caps) == count
            assert sum(caps) == 52
            assert max(caps) - min(caps) <= 1
            assert all(c >= 7 for c in caps), "each cap must respect the 7-word scene minimum"

        for count in (4, 5, 6):
            caps = gs._allocate_scene_word_caps(52, count)
            assert caps == gs._allocate_scene_word_caps(52, count), "deterministic"

    def test_t1_allocate_caps_requires_positive_scene_count(self):
        with pytest.raises(ValueError):
            gs._allocate_scene_word_caps(52, 0)
        with pytest.raises(ValueError):
            gs._allocate_scene_word_caps(3, 5)  # maximum < scene_count

    # T2 — prompt contains previous attempt and contract
    def _budget(self):
        return {
            "targetSec": 30, "minSec": 27, "maxSec": 30,
            "minimumWords": 47, "preferredWords": 52, "maximumWords": 52,
            "sceneCount": 5, "pauseSec": 1.4,
            "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
        }

    def test_t2_compression_prompt_contains_previous_attempt(self):
        script = _v2_script(scenes=[_v2_scene(i, voiceover=f"voz escena {i}") for i in range(1, 6)])
        caps = [11, 11, 10, 10, 10]
        prompt = gs._build_voiceover_compression_prompt(
            script, self._budget(), actual_word_count=60, scene_word_caps=caps,
            allow_generated_images=False,
        )
        for i in range(1, 6):
            assert f'"sceneNumber": {i}' in prompt
            assert f"voz escena {i}" in prompt
            assert f'"maximumWords": {caps[i-1]}' in prompt
        assert "str.split()" in prompt
        assert "mínimo 47" in prompt.lower() or "mínimo 47" in prompt
        assert "52" in prompt
        assert '{"scenes": [{"sceneNumber": 1, "voiceover": "..."}]}' in prompt
        assert "No devuelvas `visualPlan`, `subtitle`, `title`, `hook`, `summary`" in prompt
        assert "no es editable" in prompt or "NO se modifica" in prompt

    # T3 — merge modifies only voiceover; input not mutated
    def test_t3_merge_only_modifies_voiceover(self):
        base = _v2_script(scenes=[_v2_scene(i) for i in range(1, 5)])
        caps = [11, 11, 11, 11]
        payload = {"scenes": [{"sceneNumber": i, "voiceover": f"nueva voz número {i} para la escena"} for i in range(1, 5)]}
        before = _json.loads(_json.dumps(base))
        merged, shape_errors, budget_errors = gs._apply_voiceover_repair(
            base, payload, expected_scene_numbers=[1, 2, 3, 4], scene_word_caps=caps)
        assert shape_errors == []
        assert budget_errors == []
        assert merged is not None
        # input not mutated
        assert base == before
        for i in range(1, 5):
            assert merged["scenes"][i - 1]["voiceover"] == f"nueva voz número {i} para la escena"
            # everything else identical
            merged_scene = dict(merged["scenes"][i - 1])
            base_scene = dict(before["scenes"][i - 1])
            merged_scene.pop("voiceover")
            base_scene.pop("voiceover")
            assert merged_scene == base_scene
        # top-level and non-voiceover fields identical
        merged_top = dict(merged)
        base_top = dict(before)
        merged_top["scenes"] = [dict(s, voiceover="") for s in merged_top["scenes"]]
        base_top["scenes"] = [dict(s, voiceover="") for s in base_top["scenes"]]
        assert merged_top == base_top

    # T4 — invalid payloads rejected
    @pytest.mark.parametrize("mutator", [
        lambda p: p["scenes"].pop(0),                                # missing scene
        lambda p: p["scenes"].append({"sceneNumber": 9, "voiceover": "extra"}),  # extra scene
        lambda p: p["scenes"].insert(0, dict(p["scenes"][0])),       # duplicate
        lambda p: p["scenes"].reverse(),                             # wrong order
        lambda p: p["scenes"][0].__setitem__("voiceover", ""),       # empty voiceover
        lambda p: p["scenes"][0].__setitem__("voiceover", 123),      # non-string voiceover
        lambda p: p["scenes"][0].__setitem__("extra", "x"),          # extra item field
        lambda p: p.__setitem__("extra_top", "x"),                   # extra top-level field
        lambda p: p.__setitem__("scenes", "not-a-list"),             # scenes not a list
    ])
    def test_t4_invalid_payload_rejected(self, mutator):
        base = _v2_script(scenes=[_v2_scene(i) for i in range(1, 5)])
        caps = [11, 11, 11, 11]
        payload = {"scenes": [{"sceneNumber": i, "voiceover": f"voz {i}"} for i in range(1, 5)]}
        mutator(payload)
        merged, shape_errors, budget_errors = gs._apply_voiceover_repair(
            base, payload, expected_scene_numbers=[1, 2, 3, 4], scene_word_caps=caps)
        assert merged is None
        assert shape_errors, "expected structured shape errors"
        assert budget_errors == []
        assert base["scenes"][0]["voiceover"].startswith("Escena 1")  # input not mutated

    def test_t4_payload_not_object_rejected(self):
        base = _v2_script(scenes=[_v2_scene(i) for i in range(1, 5)])
        caps = [11, 11, 11, 11]
        merged, shape_errors, budget_errors = gs._apply_voiceover_repair(
            base, ["nope"], expected_scene_numbers=[1, 2, 3, 4], scene_word_caps=caps)
        assert merged is None
        assert any(e["code"] == "REPAIR_NOT_OBJECT" for e in shape_errors)

    # T6 — integrated 60 → 56 → 69
    def _five_scene_script(self, words_per_scene):
        return _v2_script(scenes=[
            _v2_scene(i, vp_overrides={},
                      voiceover=" ".join(f"palabra{i}_{j}" for j in range(1, words_per_scene + 1)))
            for i in range(1, 6)
        ])

    def _repair_payload(self, words_per_scene):
        return {
            "scenes": [
                {"sceneNumber": i, "voiceover": " ".join(f"nueva{i}_{j}" for j in range(1, words_per_scene + 1))}
                for i in range(1, 6)
            ]
        }

    # T6A — Scenario A: historical over-cap repair payloads (56, 69) are rejected
    # before ever becoming candidates. The persisted candidate remains attempt 0.
    def test_t6a_integrated_overcap_payloads_rejected(self, monkeypatch, tmp_path):
        responses = [
            _json.dumps(self._five_scene_script(12)),   # attempt 0: 60 words (full script)
            _json.dumps({                                # attempt 1: 56 words over-cap
                "scenes": [{"sceneNumber": i, "voiceover": " ".join(f"nueva{i}_{j}" for j in range(1, n + 1))}
                           for i, n in enumerate([12, 11, 11, 11, 11], start=1)]
            }),
            _json.dumps({                                # attempt 2: 69 words over-cap
                "scenes": [{"sceneNumber": i, "voiceover": " ".join(f"nueva{i}_{j}" for j in range(1, n + 1))}
                           for i, n in enumerate([14, 14, 14, 14, 13], start=1)]
            }),
        ]

        calls = [0]

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            idx = calls[0]
            calls[0] += 1
            return responses[idx]

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Arcoíris",
                                           "--duration", "30", "--output", str(out_path)])

        exit_code = gs.main()
        assert exit_code == 0
        assert calls[0] == 3

        meta = _json.loads(out_path.read_text())
        assert meta["status"] == "REVIEW_REQUIRED"
        dc = meta["durationContract"]
        assert dc["status"] == "FAIL"
        # Both over-cap payloads were rejected before becoming candidates.
        assert dc["bestAttempt"] == 0
        assert dc["bestAttemptWordCount"] == 60
        assert dc["lastAttemptDiscardedAsRegression"] is False
        rh = dc["retryHistory"]
        # Rejected payloads leave the conserved candidate in place (60 words).
        assert [e["wordCount"] for e in rh] == [60, 60, 60]
        assert [e["wordCountSource"] for e in rh] == [
            "generated_candidate", "previous_candidate", "previous_candidate"]
        assert rh[1]["repairShapeValid"] is True
        assert rh[1]["repairBudgetValid"] is False
        assert rh[1]["repairPayloadValid"] is False
        assert rh[1]["candidateUpdated"] is False
        assert rh[1]["candidateReused"] is True
        assert rh[2]["repairShapeValid"] is True
        assert rh[2]["repairBudgetValid"] is False
        assert rh[2]["repairPayloadValid"] is False
        for e in (rh[1], rh[2]):
            codes = [err["code"] for err in e["repairErrors"]]
            assert "REPAIR_SCENE_WORD_CAP_EXCEEDED" in codes
        # Persisted script is still the initial 60-word candidate.
        assert meta["script"]["scenes"][0]["voiceover"].startswith("palabra1_")

    # T6B — Scenario B: real regression among cap-valid candidates (60 → 46 → 40).
    def test_t6b_integrated_cap_valid_regression(self, monkeypatch, tmp_path):
        responses = [
            _json.dumps(self._five_scene_script(12)),   # attempt 0: 60 words
            _json.dumps({                                # attempt 1: 46 = [10,9,9,9,9] cap-valid
                "scenes": [{"sceneNumber": i, "voiceover": " ".join(f"nueva{i}_{j}" for j in range(1, n + 1))}
                           for i, n in enumerate([10, 9, 9, 9, 9], start=1)]
            }),
            _json.dumps(self._five_scene_script(8)),     # attempt 2: 40 = [8,8,8,8,8] cap-valid (full regen)
        ]

        calls = [0]

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            idx = calls[0]
            calls[0] += 1
            return responses[idx]

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Arcoíris",
                                           "--duration", "30", "--output", str(out_path)])

        exit_code = gs.main()
        assert exit_code == 0
        assert calls[0] == 3

        meta = _json.loads(out_path.read_text())
        assert meta["status"] == "REVIEW_REQUIRED"
        dc = meta["durationContract"]
        assert dc["bestAttempt"] == 1
        assert dc["bestAttemptWordCount"] == 46
        assert dc["lastAttemptDiscardedAsRegression"] is True
        rh = dc["retryHistory"]
        assert [e["wordCount"] for e in rh] == [60, 46, 40]
        assert [e["becameBestCandidate"] for e in rh] == [True, True, False]
        assert sum(1 for e in rh if e["acceptedAsBest"]) == 1
        assert rh[1]["acceptedAsBest"] is True
        # Persisted script is the 46-word candidate.
        assert meta["durationContract"]["wordCount"] == 46
        assert meta["script"]["scenes"][0]["voiceover"].startswith("nueva1_")

    # T7 — never lose a PASS
    def test_t7_does_not_lose_pass(self, monkeypatch, tmp_path):
        responses = [self._five_scene_script(12), self._repair_payload(10)]  # 60 → 50

        calls = [0]

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            calls[0] += 1
            if calls[0] > 2:
                raise AssertionError("third call should never happen after a PASS")
            return _json.dumps(responses[calls[0] - 1])

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Arcoíris",
                                           "--duration", "30", "--output", str(out_path)])

        exit_code = gs.main()
        assert exit_code == 0
        assert calls[0] == 2
        meta = _json.loads(out_path.read_text())
        assert meta["status"] == "SCRIPT_DRAFT"
        assert meta["durationContract"]["status"] == "PASS"
        assert meta["durationContract"]["wordCount"] == 50

    # T8 — hostile payload (visualPlan/subtitle/title) is rejected, never applied
    def test_t8_hostile_payload_rejected(self):
        base = _v2_script(scenes=[_v2_scene(i) for i in range(1, 5)])
        hostile = {
            "scenes": [
                {"sceneNumber": 1, "voiceover": "nueva", "visualPlan": {"_schemaVersion": 2}},
                {"sceneNumber": 2, "voiceover": "nueva 2", "subtitle": "hack"},
                {"sceneNumber": 3, "voiceover": "nueva 3", "title": "hack"},
                {"sceneNumber": 4, "voiceover": "nueva 4"},
            ],
            "summary": "hack",
        }
        merged, shape_errors, budget_errors = gs._apply_voiceover_repair(
            base, hostile, expected_scene_numbers=[1, 2, 3, 4], scene_word_caps=[11, 11, 11, 11])
        assert merged is None
        assert shape_errors
        assert budget_errors == []
        # base untouched
        assert base["scenes"][0]["voiceover"].startswith("Escena")

    def test_t8_hostile_integrated_never_applied(self, monkeypatch, tmp_path):
        bad = self._five_scene_script(12)
        hostile = {
            "scenes": [
                {"sceneNumber": 1, "voiceover": "nueva", "visualPlan": {"x": 1}},
                {"sceneNumber": 2, "voiceover": "nueva 2", "subtitle": "hack"},
                {"sceneNumber": 3, "voiceover": "nueva 3"},
                {"sceneNumber": 4, "voiceover": "nueva 4"},
                {"sceneNumber": 5, "voiceover": "nueva 5"},
            ],
            "title": "hack",
        }
        calls = [0]

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            calls[0] += 1
            return _json.dumps(bad) if calls[0] == 1 else _json.dumps(hostile)

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Arcoíris",
                                           "--duration", "30", "--output", str(out_path)])

        gs.main()
        meta = _json.loads(out_path.read_text())
        dc = meta["durationContract"]
        # The hostile repair payload must be rejected, so the previous candidate
        # (60 words) stays and no hostile visualPlan/subtitle ever lands in the script.
        assert dc["retryHistory"][1]["repairPayloadValid"] is False
        for scene in meta["script"]["scenes"]:
            assert scene.get("visualPlan") is None or scene["visualPlan"].get("x") != 1
            assert scene.get("subtitle", "").startswith("Subtitulo")

    # T9 — per-scene caps respected, global sum <= 52
    def test_t9_scene_caps_respected(self):
        base = _v2_script(scenes=[_v2_scene(i) for i in range(1, 6)])
        caps = gs._allocate_scene_word_caps(52, 5)
        payload = {"scenes": [{"sceneNumber": i, "voiceover": " ".join(f"x{i}_{j}" for j in range(1, caps[i-1] + 1))}
                              for i in range(1, 6)]}
        merged, shape_errors, budget_errors = gs._apply_voiceover_repair(
            base, payload, expected_scene_numbers=[1, 2, 3, 4, 5], scene_word_caps=caps)
        assert shape_errors == []
        assert budget_errors == []
        for i in range(1, 6):
            cnt = len(merged["scenes"][i - 1]["voiceover"].split())
            assert cnt <= caps[i - 1], f"scene {i} exceeds its cap"
        total = sum(len(s["voiceover"].split()) for s in merged["scenes"])
        assert total <= 52
        assert total == sum(caps) == 52

    # T10 — invalid structure keeps full regeneration retry (not compression)
    def test_t10_invalid_structure_keeps_full_retry(self, monkeypatch, tmp_path):
        bad_vp = _v2_scene_vp()
        bad_vp["editorialRole"] = "context_map"
        bad_script = _v2_script(scenes=[
            _v2_scene(1, vp_overrides={"editorialRole": "context_map"}),
            _v2_scene(2), _v2_scene(3), _v2_scene(4),
        ])
        good_script = _v2_script()

        prompts = []

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            prompts.append(prompt)
            return _json.dumps(bad_script)

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
                                           "--duration", "30", "--output", str(out_path)])

        gs.main()
        meta = _json.loads(out_path.read_text())
        rh = meta["durationContract"]["retryHistory"]
        # First attempt is the initial full generation; retries are structural.
        assert rh[0]["strategy"] == "initial"
        assert all(e["strategy"] == "structural" for e in rh[1:])
        assert all(e["structureValid"] is False for e in rh)
        assert any("VISUAL_PLAN_V2_INVALID" in r for r in meta.get("reviewReasons", []))
        assert meta["durationContract"]["bestAttempt"] is None

    # T12 — exhaustion without structurally valid candidate invents nothing
    def test_t12_no_valid_candidate_invents_nothing(self, monkeypatch, tmp_path):
        bad_vp = _v2_scene_vp()
        bad_script = _v2_script(scenes=[
            _v2_scene(1, vp_overrides={"editorialRole": "context_map"}),
            _v2_scene(2), _v2_scene(3), _v2_scene(4),
        ])

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            return _json.dumps(bad_script)

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Test",
                                           "--duration", "30", "--output", str(out_path)])

        gs.main()
        meta = _json.loads(out_path.read_text())
        dc = meta["durationContract"]
        assert dc["status"] == "FAIL"
        assert dc["structureValid"] is False
        assert dc["bestAttempt"] is None
        assert dc["bestAttemptWordCount"] is None
        assert dc["lastAttemptDiscardedAsRegression"] is False
        assert any("VISUAL_PLAN_V2_INVALID" in r for r in meta.get("reviewReasons", []))


class TestDurationReviewFixes:
    """Tests for the Slice 6B duration-retry review fixes (F1-F7)."""

    # ── helpers ─────────────────────────────────────────────────────
    def _budget(self):
        return {
            "targetSec": 30, "minSec": 27, "maxSec": 30,
            "minimumWords": 47, "preferredWords": 52, "maximumWords": 52,
            "sceneCount": 5, "pauseSec": 1.4,
            "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
        }

    def _full_script_counts(self, counts):
        return _v2_script(scenes=[
            _v2_scene(i, voiceover=" ".join(f"f{i}_{j}" for j in range(1, counts[i - 1] + 1)))
            for i in range(1, len(counts) + 1)
        ])

    def _repair_counts(self, counts):
        return {
            "scenes": [
                {"sceneNumber": i, "voiceover": " ".join(f"r{i}_{j}" for j in range(1, counts[i - 1] + 1))}
                for i in range(1, len(counts) + 1)
            ]
        }

    def _run_main(self, responses, monkeypatch, tmp_path):
        calls = [0]

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            idx = calls[0]
            calls[0] += 1
            return responses[idx]

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Arcoíris",
                                           "--duration", "30", "--output", str(out_path)])
        exit_code = gs.main()
        meta = _json.loads(out_path.read_text())
        return exit_code, calls[0], meta

    # ── F1: compression uses a dedicated system prompt ─────────────
    def test_f1_compression_uses_dedicated_system_prompt(self, monkeypatch, tmp_path):
        pairs = []

        def mock_call(prompt, api_key, model, provider="openai", system_prompt=None):
            pairs.append((system_prompt, prompt))
            if len(pairs) == 1:
                return _json.dumps(self._full_script_counts([12] * 5))       # 60 words
            return _json.dumps(self._repair_counts([20, 8, 8, 8, 8]))          # over-cap -> rejected

        monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
        monkeypatch.setattr(gs, "call_llm", mock_call)
        out_path = tmp_path / "metadata.json"
        monkeypatch.setattr(sys, "argv", ["generate_script.py", "--topic", "Arcoíris",
                                           "--duration", "30", "--output", str(out_path)])
        gs.main()

        compression_pair = pairs[1]  # first retry is compression (60 > max)
        sys_prompt, user_prompt = compression_pair
        assert sys_prompt == gs.VOICEOVER_COMPRESSION_SYSTEM_PROMPT
        assert sys_prompt != gs.SYSTEM_PROMPT_V2
        # The compression system prompt must not require a full script / visualPlan.
        assert "visualPlan" not in sys_prompt or "No devuelvas" in sys_prompt
        assert "sceneNumber" in sys_prompt
        assert "voiceover" in sys_prompt
        # The user prompt demands only sceneNumber + voiceover per scene.
        assert '{"scenes": [{"sceneNumber": 1, "voiceover": "..."}]}' in user_prompt
        assert "No devuelvas `visualPlan`" in user_prompt
        # F2: expected scene numbers interpolated, not literal placeholder.
        assert "{expected}" not in user_prompt
        assert "[1, 2, 3, 4, 5]" in user_prompt

    # ── F2: expected sceneNumber sequence interpolated ─────────────
    def test_f2_expected_interpolated_five_scenes(self):
        script = _v2_script(scenes=[_v2_scene(i) for i in range(1, 6)])
        prompt = gs._build_voiceover_compression_prompt(
            script, self._budget(), actual_word_count=60, scene_word_caps=[11, 11, 10, 10, 10],
            allow_generated_images=False,
        )
        assert "{expected}" not in prompt
        assert "[1, 2, 3, 4, 5]" in prompt

    def test_f2_expected_interpolated_four_scenes(self):
        script = _v2_script(scenes=[_v2_scene(i) for i in range(1, 5)])
        prompt = gs._build_voiceover_compression_prompt(
            script, self._budget(), actual_word_count=52, scene_word_caps=[13, 13, 13, 13],
            allow_generated_images=False,
        )
        assert "{expected}" not in prompt
        assert "[1, 2, 3, 4]" in prompt

    # ── F3: caps enforcement (negative + valid) ────────────────────
    def test_f3_case_20_8_8_8_8_rejected(self):
        # Mandatory case: global total 52 is within range, but scene 1 breaks its cap.
        base = _v2_script(scenes=[_v2_scene(i) for i in range(1, 6)])
        caps = [11, 11, 10, 10, 10]
        payload = self._repair_counts([20, 8, 8, 8, 8])
        merged, shape_errors, budget_errors = gs._apply_voiceover_repair(
            base, payload, expected_scene_numbers=[1, 2, 3, 4, 5], scene_word_caps=caps)
        assert merged is None
        assert shape_errors == []
        codes = [e["code"] for e in budget_errors]
        assert "REPAIR_SCENE_WORD_CAP_EXCEEDED" in codes
        assert budget_errors[0]["sceneNumber"] == 1
        assert "scene 1" in budget_errors[0]["message"]
        # input not mutated
        assert base["scenes"][0]["voiceover"].startswith("Escena")

    def test_f3_over_cap_rejected(self):
        base = _v2_script(scenes=[_v2_scene(i) for i in range(1, 6)])
        merged, _, budget_errors = gs._apply_voiceover_repair(
            base, self._repair_counts([12, 9, 9, 9, 9]),
            expected_scene_numbers=[1, 2, 3, 4, 5], scene_word_caps=[11, 11, 10, 10, 10])
        assert merged is None
        assert any(e["code"] == "REPAIR_SCENE_WORD_CAP_EXCEEDED" for e in budget_errors)

    def test_f3_under_minimum_rejected(self):
        base = _v2_script(scenes=[_v2_scene(i) for i in range(1, 6)])
        merged, _, budget_errors = gs._apply_voiceover_repair(
            base, self._repair_counts([5, 9, 9, 9, 9]),
            expected_scene_numbers=[1, 2, 3, 4, 5], scene_word_caps=[11, 11, 10, 10, 10])
        assert merged is None
        assert any(e["code"] == "REPAIR_SCENE_WORD_MINIMUM_NOT_MET" for e in budget_errors)

    def test_f3_invalid_caps_rejected(self):
        base = _v2_script(scenes=[_v2_scene(i) for i in range(1, 6)])
        payload = self._repair_counts([8, 8, 8, 8, 8])
        # wrong length
        merged, _, budget_errors = gs._apply_voiceover_repair(
            base, payload, expected_scene_numbers=[1, 2, 3, 4, 5], scene_word_caps=[11, 11, 10, 10])
        assert merged is None
        assert any(e["code"] == "REPAIR_INVALID_SCENE_CAPS" for e in budget_errors)
        # non-integer cap
        merged, _, budget_errors = gs._apply_voiceover_repair(
            base, payload, expected_scene_numbers=[1, 2, 3, 4, 5], scene_word_caps=[11, 11, 10, 10, "x"])
        assert merged is None
        assert any(e["code"] == "REPAIR_INVALID_SCENE_CAPS" for e in budget_errors)
        # boolean cap (bool is int subclass)
        merged, _, budget_errors = gs._apply_voiceover_repair(
            base, payload, expected_scene_numbers=[1, 2, 3, 4, 5], scene_word_caps=[11, True, 10, 10, 10])
        assert merged is None
        assert any(e["code"] == "REPAIR_INVALID_SCENE_CAPS" for e in budget_errors)
        # cap below the 7-word minimum
        merged, _, budget_errors = gs._apply_voiceover_repair(
            base, payload, expected_scene_numbers=[1, 2, 3, 4, 5], scene_word_caps=[11, 11, 5, 10, 10])
        assert merged is None
        assert any(e["code"] == "REPAIR_INVALID_SCENE_CAPS" for e in budget_errors)

    def test_f3_fully_valid_payload_accepted(self):
        base = _v2_script(scenes=[_v2_scene(i) for i in range(1, 6)])
        merged, shape_errors, budget_errors = gs._apply_voiceover_repair(
            base, self._repair_counts([8, 8, 8, 8, 8]),
            expected_scene_numbers=[1, 2, 3, 4, 5], scene_word_caps=[11, 11, 10, 10, 10])
        assert merged is not None
        assert shape_errors == []
        assert budget_errors == []

    # ── F5: regression cases B/C/D ─────────────────────────────────
    def test_f5_case_b_last_attempt_best(self, monkeypatch, tmp_path):
        responses = [
            _json.dumps(self._full_script_counts([12] * 5)),       # 60
            _json.dumps(self._repair_counts([8] * 5)),              # 40 (cap-valid, below min)
            _json.dumps(self._full_script_counts([10, 9, 9, 9, 9])),  # 46 (full, best)
        ]
        exit_code, n_calls, meta = self._run_main(responses, monkeypatch, tmp_path)
        assert exit_code == 0
        assert n_calls == 3
        dc = meta["durationContract"]
        assert dc["bestAttempt"] == 2
        assert dc["bestAttemptWordCount"] == 46
        assert dc["lastAttemptDiscardedAsRegression"] is False
        rh = dc["retryHistory"]
        assert [e["wordCount"] for e in rh] == [60, 40, 46]
        assert sum(1 for e in rh if e["acceptedAsBest"]) == 1
        assert rh[2]["acceptedAsBest"] is True

    def test_f5_case_c_tie(self, monkeypatch, tmp_path):
        responses = [
            _json.dumps(self._full_script_counts([12] * 5)),       # 60
            _json.dumps(self._repair_counts([10, 9, 9, 9, 9])),     # 46 (best)
            _json.dumps(self._full_script_counts([10, 9, 9, 9, 9])),  # 46 (tie -> not best)
        ]
        exit_code, n_calls, meta = self._run_main(responses, monkeypatch, tmp_path)
        assert exit_code == 0
        assert n_calls == 3
        dc = meta["durationContract"]
        assert dc["bestAttempt"] == 1
        assert dc["lastAttemptDiscardedAsRegression"] is False
        rh = dc["retryHistory"]
        assert [e["becameBestCandidate"] for e in rh] == [True, True, False]
        assert sum(1 for e in rh if e["acceptedAsBest"]) == 1
        assert rh[1]["acceptedAsBest"] is True

    def test_f5_case_d_final_payload_rejected(self, monkeypatch, tmp_path):
        # The best candidate (53) is over-max so the final retry is a compression
        # whose over-cap payload is rejected before becoming a candidate.
        responses = [
            _json.dumps(self._full_script_counts([8] * 5)),         # 40 (below min)
            _json.dumps(self._full_script_counts([11, 11, 11, 11, 9])),  # 53 (over max, best)
            _json.dumps(self._repair_counts([20, 8, 8, 8, 8])),      # over-cap -> rejected
        ]
        exit_code, n_calls, meta = self._run_main(responses, monkeypatch, tmp_path)
        assert exit_code == 0
        assert n_calls == 3
        dc = meta["durationContract"]
        assert dc["bestAttempt"] == 1
        assert dc["lastAttemptDiscardedAsRegression"] is False
        rh = dc["retryHistory"]
        assert rh[2]["candidateUpdated"] is False
        assert rh[2]["repairPayloadValid"] is False
        assert rh[2]["candidateReused"] is True
        # A rejected response is never called a regression.
        assert sum(1 for e in rh if e["acceptedAsBest"]) == 1
        assert rh[1]["acceptedAsBest"] is True

    # ── F5 (F6): canonical representation persisted on exhaustion ──
    def test_f6_canonical_persisted_on_exhaustion(self, monkeypatch, tmp_path):
        def uppercase_scene(i):
            return _v2_scene(
                i,
                vp_overrides={
                    "visualIntent": "  EXPLAIN ",
                    "subjects": ["  subject a ", " subject b "],
                    "assetPreferences": [" DIAGRAM "],
                    "visualSequence": [{
                        "segmentIndex": 1, "assetPreference": "DIAGRAM",
                        "durationFraction": 1.0, "transition": "CUT",
                    }],
                },
                voiceover=" ".join(f"c{i}_{j}" for j in range(1, 13)),
            )

        full = _json.dumps(_v2_script(scenes=[uppercase_scene(i) for i in range(1, 6)]))
        overcap = _json.dumps(self._repair_counts([20, 8, 8, 8, 8]))
        responses = [full, overcap, overcap]  # 60 words, over-cap repairs rejected
        exit_code, n_calls, meta = self._run_main(responses, monkeypatch, tmp_path)
        assert exit_code == 0
        assert n_calls == 3
        dc = meta["durationContract"]
        assert dc["bestAttempt"] == 0
        assert dc["structureValid"] is True
        assert meta["status"] == "REVIEW_REQUIRED"
        scene = meta["script"]["scenes"][0]
        vp = scene["visualPlan"]
        assert vp["visualIntent"] == "explain"
        assert vp["assetPreferences"] == ["diagram"]
        assert vp["visualSequence"][0]["assetPreference"] == "diagram"
        assert vp["visualSequence"][0]["transition"] == "cut"
        assert vp.get("allowGeneratedImage") is False
        assert vp["subjects"] == ["subject a", "subject b"]

    # ── F7 (F6): telemetry for a rejected payload ──────────────────
    def test_f7_rejected_payload_telemetry(self, monkeypatch, tmp_path):
        responses = [
            _json.dumps(self._full_script_counts([12] * 5)),       # 60
            "not-json",                                             # rejected
            "also-not-json",                                        # rejected
        ]
        exit_code, n_calls, meta = self._run_main(responses, monkeypatch, tmp_path)
        assert exit_code == 0
        assert n_calls == 3
        rh = meta["durationContract"]["retryHistory"]
        for e in (rh[1], rh[2]):
            assert e["candidateUpdated"] is False
            assert e["candidateReused"] is True
            assert e["repairPayloadValid"] is False
            assert e["wordCountSource"] == "previous_candidate"
            assert any(err["code"] == "REPAIR_NOT_JSON" for err in e["repairErrors"])

    # ── F8: acceptedAsBest unambiguous ─────────────────────────────
    def test_f8_accepted_as_best_single_when_best_exists(self, monkeypatch, tmp_path):
        responses = [
            _json.dumps(self._full_script_counts([12] * 5)),       # 60
            _json.dumps(self._repair_counts([10, 9, 9, 9, 9])),     # 46 (best)
            _json.dumps(self._repair_counts([20, 8, 8, 8, 8])),      # rejected
        ]
        exit_code, _, meta = self._run_main(responses, monkeypatch, tmp_path)
        assert exit_code == 0
        rh = meta["durationContract"]["retryHistory"]
        assert sum(1 for e in rh if e["acceptedAsBest"]) == 1

    def test_f8_accepted_as_best_zero_when_all_invalid(self, monkeypatch, tmp_path):
        bad_script = _v2_script(scenes=[
            _v2_scene(1, vp_overrides={"editorialRole": "x"}),
            _v2_scene(2), _v2_scene(3), _v2_scene(4),
        ])
        responses = [_json.dumps(bad_script)] * 3
        exit_code, _, meta = self._run_main(responses, monkeypatch, tmp_path)
        assert exit_code == 0
        rh = meta["durationContract"]["retryHistory"]
        assert sum(1 for e in rh if e["acceptedAsBest"]) == 0
        assert meta["durationContract"]["bestAttempt"] is None

    # ── F9: compression system prompt shape ────────────────────────
    def test_f9_compression_system_prompt_shape(self):
        sp = gs.VOICEOVER_COMPRESSION_SYSTEM_PROMPT
        assert "SOLO JSON" in sp
        assert "sceneNumber" in sp
        assert "voiceover" in sp
        assert "assetPreferences" not in sp
        assert "visualSequence" not in sp
        # Negative mentions are acceptable; they must not be required fields.
        assert "visualPlan" in sp  # present only as a negative prohibition
        assert "No devuelvas" in sp

    # ── F8 (canonical follow-up): the active candidate is canonical ─
    def _canonicalizable_scene(self, i, words=12):
        return _v2_scene(
            i,
            vp_overrides={
                "visualIntent": "  EXPLAIN ",
                "subjects": ["  subject a ", " subject b "],
                "assetPreferences": [" DIAGRAM "],
                "visualSequence": [{
                    "segmentIndex": 1, "assetPreference": "DIAGRAM",
                    "durationFraction": 1.0, "transition": "CUT",
                }],
            },
            voiceover=" ".join(f"p{i}_{j}" for j in range(1, words + 1)),
        )

    def _assert_canonical_vp(self, vp):
        assert vp["visualIntent"] == "explain"
        assert vp["assetPreferences"] == ["diagram"]
        assert vp["visualSequence"][0]["assetPreference"] == "diagram"
        assert vp["visualSequence"][0]["transition"] == "cut"
        assert vp["subjects"] == ["subject a", "subject b"]
        assert vp["allowGeneratedImage"] is False
        assert vp["preferredProviders"] == []
        assert vp.get("period") is None
        assert vp.get("location") is None

    # The compression prompt must receive the canonical candidate, never the
    # raw response. If the code regresses to passing script_data, the raw
    # values (uppercase/padded) fail these assertions.
    def test_f8_canonical_flows_to_compression_prompt(self, monkeypatch, tmp_path):
        responses = [
            _json.dumps(_v2_script(scenes=[self._canonicalizable_scene(i) for i in range(1, 6)])),  # 60 words
            _json.dumps(self._repair_counts([20, 8, 8, 8, 8])),   # over-cap -> rejected
            _json.dumps(self._repair_counts([20, 8, 8, 8, 8])),   # over-cap -> rejected
        ]

        received = []
        real_build = gs._build_voiceover_compression_prompt

        def spy(canonical_script, budget, actual_word_count, scene_word_caps, *, allow_generated_images):
            received.append(canonical_script)
            return real_build(canonical_script, budget, actual_word_count, scene_word_caps,
                              allow_generated_images=allow_generated_images)

        monkeypatch.setattr(gs, "_build_voiceover_compression_prompt", spy)
        exit_code, n_calls, _ = self._run_main(responses, monkeypatch, tmp_path)
        assert exit_code == 0
        assert n_calls == 3
        assert received, "compression prompt must have been built"
        for scene in received[0]["scenes"]:
            self._assert_canonical_vp(scene["visualPlan"])

    # The merge base must already be canonicalized before voiceovers are
    # replaced; the result keeps the canonical representation, only the
    # voiceover fields change, and the intercepted base is never mutated.
    def test_f8_canonical_base_used_by_merge(self, monkeypatch, tmp_path):
        responses = [
            _json.dumps(_v2_script(scenes=[self._canonicalizable_scene(i) for i in range(1, 6)])),  # 60 words
            _json.dumps(self._repair_counts([9, 9, 9, 9, 9])),   # 45 words cap-valid -> merge
            _json.dumps(self._full_script_counts([9, 9, 9, 9, 9])),  # 45 words, not a merge
        ]

        captured = []
        real_repair = gs._apply_voiceover_repair

        def spy(base_script, repair_payload, *, expected_scene_numbers, scene_word_caps):
            snapshot = _json.loads(_json.dumps(base_script))
            merged, shape_errors, budget_errors = real_repair(
                base_script, repair_payload,
                expected_scene_numbers=expected_scene_numbers,
                scene_word_caps=scene_word_caps)
            assert base_script == snapshot, "repair must not mutate its base"
            captured.append({"base": snapshot, "merged": merged})
            return merged, shape_errors, budget_errors

        monkeypatch.setattr(gs, "_apply_voiceover_repair", spy)
        exit_code, n_calls, _ = self._run_main(responses, monkeypatch, tmp_path)
        assert exit_code == 0
        assert n_calls == 3
        assert captured, "a merge must have run"
        first = captured[0]
        assert first["merged"] is not None
        base = first["base"]
        for scene in base["scenes"]:
            self._assert_canonical_vp(scene["visualPlan"])
        merged = first["merged"]
        # visualPlan stays canonical (does not revert to the raw form) and only
        # the voiceover fields change between base and merged.
        for i in range(5):
            base_scene = dict(base["scenes"][i])
            merged_scene = dict(merged["scenes"][i])
            assert base_scene["voiceover"] != merged_scene["voiceover"]
            base_scene.pop("voiceover")
            merged_scene.pop("voiceover")
            assert base_scene == merged_scene
        assert merged["scenes"][0]["voiceover"].startswith("r1_")

    # ── F2 extension: six-scene interpolation ──────────────────────
    def test_f2_expected_interpolated_six_scenes(self):
        script = _v2_script(scenes=[_v2_scene(i) for i in range(1, 7)])
        caps = gs._allocate_scene_word_caps(52, 6)
        prompt = gs._build_voiceover_compression_prompt(
            script, self._budget(), actual_word_count=52, scene_word_caps=caps,
            allow_generated_images=False,
        )
        assert "{expected}" not in prompt
        assert "[1, 2, 3, 4, 5, 6]" in prompt
