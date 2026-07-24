import sys
from pathlib import Path

# Allow test to import modules from bin/
_BIN = Path(__file__).resolve().parents[1] / "bin"
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))


# ── V2 validation tests ────────────────────────────────────────────────

import json as _json


def _v2_vp(**overrides):
    """Minimal valid V2 visualPlan."""
    vp = {
        "_schemaVersion": 2,
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


def _v2_scene(num, voiceover=None):
    """Valid V2 scene."""
    return {
        "sceneNumber": num,
        "voiceover": voiceover or f"Escena {num} del guion divulgativo con contenido narrativo suficiente.",
        "subtitle": f"S{num}",
        "targetDurationSec": 7.5,
        "visualPlan": _v2_vp(),
    }


_v2_long_vo = " ".join(["concepto divulgativo explicativo"] * 4)  # ~13 words per scene, ~52 total for 4 scenes
_V2_VALID_4_SCENE = {
    "title": "Test",
    "scenes": [_v2_scene(i, voiceover=_v2_long_vo) for i in range(1, 5)],
}

_many_words_v2 = " ".join(["concepto divulgativo"] * 15)
_V2_ABOVE_MAX_WORDS = {
    "title": "Test",
    "scenes": [_v2_scene(i, voiceover=_many_words_v2) for i in range(1, 5)],
}

_V2_SINGLE_SCENE_CTA = {
    "title": "Test",
    "scenes": [
        {"sceneNumber": 1, "voiceover": "Suscríbete para más videos. ¡Gracias!",
         "subtitle": "CTA", "targetDurationSec": 3.0,
         "visualPlan": _v2_vp()}
    ],
}


def test_max_script_attempts_is_three():
    """MAX_SCRIPT_ATTEMPTS permits initial generation + up to 2 retries."""
    from generate_script import MAX_SCRIPT_ATTEMPTS
    assert MAX_SCRIPT_ATTEMPTS == 3, (
        f"Expected MAX_SCRIPT_ATTEMPTS=3 (initial + 2 retries), got {MAX_SCRIPT_ATTEMPTS}"
    )


def test_main_retry_loop_3_attempts_3rd_succeeds(monkeypatch, tmp_path):
    """Integration: main() calls LLM 3 times, retry 1 has V2 structural issue,
    retry 2 is structural CTA (insufficient scenes), retry 3 produces valid V2 script → SCRIPT_DRAFT."""
    import sys as _sys
    import generate_script as gs

    out = tmp_path / "metadata.json"

    # Response 1: valid V2 but above max words
    resp_1 = _json.dumps(_V2_ABOVE_MAX_WORDS)
    # Response 2: structural failure — single scene (V2 requires 4-6)
    resp_2 = _json.dumps(_V2_SINGLE_SCENE_CTA)
    # Response 3: valid V2
    resp_3 = _json.dumps(_V2_VALID_4_SCENE)

    call_count = [0]
    prompts_seen = []

    def m_call_llm(prompt, api_key, model, provider="openai", system_prompt=None):
        call_count[0] += 1
        prompts_seen.append(prompt)
        if call_count[0] == 1:
            return resp_1
        elif call_count[0] == 2:
            return resp_2
        else:
            return resp_3

    monkeypatch.setattr(gs, "call_llm", m_call_llm)
    monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake", "LLM_PROVIDER": "openai"})
    monkeypatch.setattr(_sys, "argv", ["generate_script.py", "--topic", "Test", "--duration", "30",
                                        "--output", str(out)])

    exit_code = gs.main()
    assert exit_code == 0

    assert call_count[0] == 3, f"Expected 3 LLM calls, got {call_count[0]}"

    meta = _json.loads(out.read_text())
    assert meta["status"] == "SCRIPT_DRAFT"
    assert meta["durationContract"]["status"] == "PASS"
    assert meta["durationContract"]["structureValid"] is True
    rh = meta["durationContract"]["retryHistory"]
    assert len(rh) == 3
    assert rh[0]["reason"] == "above_maximum_words"
    assert "INSUFFICIENT_SCENE_COUNT" in rh[1]["reason"]
    assert rh[2]["reason"] == "in_range"


def test_main_retry_loop_3_attempts_all_fail_review_required(monkeypatch, tmp_path):
    """Integration: main() calls LLM 3 times, all fail V2 validation → REVIEW_REQUIRED."""
    import sys as _sys
    import generate_script as gs

    out = tmp_path / "metadata.json"
    # Single-scene response fails V2 validation (needs 4-6 scenes)
    resp = _json.dumps(_V2_SINGLE_SCENE_CTA)

    call_count = [0]
    def m_call_llm(prompt, api_key, model, provider="openai", system_prompt=None):
        call_count[0] += 1
        return resp

    monkeypatch.setattr(gs, "call_llm", m_call_llm)
    monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake", "LLM_PROVIDER": "openai"})
    monkeypatch.setattr(_sys, "argv", ["generate_script.py", "--topic", "Test", "--duration", "30",
                                        "--output", str(out)])

    exit_code = gs.main()
    assert exit_code == 0  # main returns 0; status REVIEW_REQUIRED is stored in metadata

    assert call_count[0] == 3
    meta = _json.loads(out.read_text())
    assert meta["status"] == "REVIEW_REQUIRED"
    assert meta["durationContract"]["status"] == "FAIL"
    assert meta["durationContract"]["structureValid"] is False
    assert len(meta["durationContract"]["structureIssues"]) >= 1
    rh = meta["durationContract"]["retryHistory"]
    assert len(rh) == 3
    assert "structuralIssues" in rh[2]


def test_fetch_images_imports_editorial_contract():
    """fetch_images imports the shared legacy editorial contract directly."""
    import editorial_asset_contract as eac
    assert hasattr(eac, "EDITORIAL_ROLE_PREFERENCES")
    assert hasattr(eac, "is_asset_type_allowed")

    import fetch_images as fi
    assert fi.EDITORIAL_ROLE_PREFERENCES is eac.EDITORIAL_ROLE_PREFERENCES
    assert fi.is_asset_type_allowed is eac.is_asset_type_allowed


def test_validate_segment_for_role_uses_shared_helper():
    """_validate_segment_for_role must delegate to is_asset_type_allowed
    for requested-type checks."""
    import fetch_images as fi
    import inspect
    src = inspect.getsource(fi._validate_segment_for_role)
    assert "is_asset_type_allowed" in src, (
        "_validate_segment_for_role must use is_asset_type_allowed"
    )
    # Must not replicate the exception locally
    loc = src.find("is_asset_type_allowed")
    after = src[loc:] if loc >= 0 else src
    assert '.discard("atmospheric_broll")' not in after, (
        "_validate_segment_for_role must not locally discard atmospheric_broll"
    )


def test_fetch_images_no_duplicate_atmospheric_discard():
    """The only .discard("atmospheric_broll") must be in
    editorial_asset_contract.py, not duplicated in fetch_images."""
    import fetch_images as fi
    import inspect
    foa_src = inspect.getsource(fi._fetch_one_asset)
    assert '.discard("atmospheric_broll")' not in foa_src, (
        "_fetch_one_asset must not locally discard atmospheric_broll"
    )


# ── Role/intent/type contract tests ─────────────────────────────────────


def test_unknown_role_fails_closed():
    from editorial_asset_contract import is_asset_type_allowed
    assert not is_asset_type_allowed("nonexistent_role", "historical_photograph")


def test_unknown_asset_type_fails_closed():
    from editorial_asset_contract import is_asset_type_allowed
    assert not is_asset_type_allowed("context_map", "nonexistent_type")


def test_aliases_map_or_document_accepted_for_context_map():
    from editorial_asset_contract import is_asset_type_allowed
    assert is_asset_type_allowed("context_map", "map_or_document")


def test_aliases_historical_map_or_document_accepted():
    from editorial_asset_contract import is_asset_type_allowed
    assert is_asset_type_allowed("context_map", "historical_map_or_document")
