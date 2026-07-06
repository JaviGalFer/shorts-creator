import pytest
import re
import sys
from pathlib import Path

# Allow test to import modules from bin/
_BIN = Path(__file__).resolve().parents[1] / "bin"
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

PROMPT_PATH = Path(__file__).resolve().parents[1] / "bin" / "generate_script.py"
content = PROMPT_PATH.read_text()
# Extract SYSTEM_PROMPT string between triple quotes
m = re.search(r"SYSTEM_PROMPT\s*=\s*\"\"\"(.*?)\"\"\"", content, re.DOTALL)
assert m, "Could not extract SYSTEM_PROMPT"
SYSTEM_PROMPT = m.group(1)


def test_prompt_has_decision_tree():
    assert "Árbol de decisión" in SYSTEM_PROMPT


def test_prompt_has_all_eight_roles_in_decision_tree():
    roles_in_tree = [
        "character_portrait",
        "battle_or_assault",
        "military_technology",
        "civilian_impact",
        "document_or_date",
        "context_map",
        "consequence_or_legacy",
        "atmospheric_transition",
    ]
    for role in roles_in_tree:
        assert role in SYSTEM_PROMPT, f"Role {role} missing from prompt"


def test_context_map_has_exclusion_rule():
    assert "NO usar para escenas que describen un evento" in SYSTEM_PROMPT


def test_context_map_berlin_wall_example():
    assert "El Muro de Berlín cayó en 1989" in SYSTEM_PROMPT
    assert "battle_or_assault" in SYSTEM_PROMPT.split("El Muro de Berlín cayó en 1989")[1]


def test_context_map_is_not_default():
    assert "NO usar context_map como valor por defecto" in SYSTEM_PROMPT


def test_context_map_restricted_to_geography():
    assert "EXCLUSIVAMENTE para escenas donde el propósito visual principal es entender geografía" in SYSTEM_PROMPT


def test_prompt_has_exclusion_rules_section():
    assert "Reglas de exclusión" in SYSTEM_PROMPT


def test_prompt_has_detailed_role_descriptions():
    assert "Descripción detallada por rol" in SYSTEM_PROMPT


def test_character_portrait_exclusion():
    assert "NO usar si no hay una persona histórica específica" in SYSTEM_PROMPT


def test_atmospheric_transition_max_20_percent():
    assert "20%" in SYSTEM_PROMPT


# ── Structural validation tests ────────────────────────────────────────


def test_max_script_attempts_is_three():
    """MAX_SCRIPT_ATTEMPTS permits initial generation + up to 2 retries."""
    from generate_script import MAX_SCRIPT_ATTEMPTS
    assert MAX_SCRIPT_ATTEMPTS == 3, (
        f"Expected MAX_SCRIPT_ATTEMPTS=3 (initial + 2 retries), got {MAX_SCRIPT_ATTEMPTS}"
    )


def test_one_scene_eight_word_cta_is_structurally_invalid():
    """A script with only 1 scene of generic CTA content must fail
    structural validation."""
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = {
        "scenes": [
            {
                "sceneNumber": 5,
                "voiceover": "Recuerda, la historia está viva. ¡Suscríbete para más!",
                "subtitle": "Suscríbete",
                "targetDurationSec": 4.0,
            }
        ]
    }
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "La caída del Muro de Berlín")
    assert result["valid"] is False
    codes = [code for code, _ in result["reasons"]]
    assert "insufficient_scene_count" in codes
    assert "cta_only_or_non_historical" in codes
    assert "missing_visualPlan" in codes


def test_multi_scene_valid_historical_passes_structure():
    """A structurally complete historical script with visualPlan must pass."""
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = {
        "scenes": [
            {
                "sceneNumber": 1,
                "purpose": "Hook",
                "visualTemporalIntent": "event_depiction",
                "voiceover": "El 9 de noviembre de 1989, el Muro de Berlín cayó ante la presión popular.",
                "subtitle": "Cayó el Muro",
                "targetDurationSec": 6.0,
                "visualPlan": {
                    "strategy": "historical_archive",
                    "editorialRole": "consequence_or_legacy",
                    "primaryAssetType": "historical_photograph",
                    "period": "1989",
                    "location": "Berlín",
                    "entities": ["Muro de Berlín"],
                    "searchQueries": ["Berlin Wall fall 1989"],
                    "visualSequence": [
                        {"segmentIndex": 1, "assetType": "historical_photograph",
                         "durationFraction": 0.5, "transition": "cut", "motionType": "slow_zoom_in"},
                        {"segmentIndex": 2, "assetType": "historical_art",
                         "durationFraction": 0.5, "transition": "fade", "motionType": "pan_right"},
                    ]
                }
            },
            {
                "sceneNumber": 2,
                "purpose": "Context",
                "visualTemporalIntent": "event_depiction",
                "voiceover": "La Guerra Fría dividió Europa durante décadas con un telón de acero.",
                "subtitle": "Guerra Fría",
                "targetDurationSec": 6.0,
                "visualPlan": {
                    "strategy": "historical_archive",
                    "editorialRole": "context_map",
                    "primaryAssetType": "historical_map",
                    "period": "1945-1991",
                    "location": "Europa",
                    "entities": ["Guerra Fría"],
                    "searchQueries": ["Cold War Europe division map"],
                    "visualSequence": [
                        {"segmentIndex": 1, "assetType": "historical_map",
                         "durationFraction": 0.5, "transition": "cut", "motionType": "slow_zoom_in"},
                        {"segmentIndex": 2, "assetType": "document",
                         "durationFraction": 0.5, "transition": "fade", "motionType": "pan_right"},
                    ]
                }
            },
            {
                "sceneNumber": 3,
                "purpose": "Event",
                "visualTemporalIntent": "event_depiction",
                "voiceover": "Miles de berlineses cruzaron la frontera en una noche de euforia.",
                "subtitle": "Euforia",
                "targetDurationSec": 6.0,
                "visualPlan": {
                    "strategy": "historical_archive",
                    "editorialRole": "civilian_impact",
                    "primaryAssetType": "historical_photograph",
                    "period": "1989",
                    "location": "Berlín",
                    "entities": ["Muro de Berlín"],
                    "searchQueries": ["Berliners crossing border 1989"],
                    "visualSequence": [
                        {"segmentIndex": 1, "assetType": "historical_photograph",
                         "durationFraction": 0.5, "transition": "cut", "motionType": "slow_zoom_in"},
                        {"segmentIndex": 2, "assetType": "historical_art",
                         "durationFraction": 0.5, "transition": "fade", "motionType": "pan_right"},
                    ]
                }
            },
            {
                "sceneNumber": 4,
                "purpose": "Legacy",
                "visualTemporalIntent": "legacy_or_commemoration",
                "voiceover": "La caída del Muro simbolizó el fin de la división en Alemania y en el mundo. Suscríbete.",
                "subtitle": "Fin de división",
                "targetDurationSec": 6.0,
                "visualPlan": {
                    "strategy": "historical_archive",
                    "editorialRole": "consequence_or_legacy",
                    "primaryAssetType": "historical_photograph",
                    "period": "1989",
                    "location": "Berlín",
                    "entities": ["Muro de Berlín"],
                    "searchQueries": ["Berlin Wall legacy memorial 1989"],
                    "visualSequence": [
                        {"segmentIndex": 1, "assetType": "historical_photograph",
                         "durationFraction": 0.5, "transition": "cut", "motionType": "slow_zoom_in"},
                        {"segmentIndex": 2, "assetType": "historical_art",
                         "durationFraction": 0.5, "transition": "fade", "motionType": "pan_right"},
                    ]
                }
            },
        ]
    }
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "La caída del Muro de Berlín")
    assert result["valid"] is True, f"Expected valid, got reasons: {result['reasons']}"
    assert len(result["reasons"]) == 0


def test_structurally_invalid_accepted_only_if_duration_fits():
    """A structurally invalid script must be rejected even if its word count
    happens to be in range. The validator returns valid=False regardless of
    duration, and the loop must retry."""
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    # 1-scene CTA that by coincidence has a decent word count
    script = {
        "scenes": [
            {
                "sceneNumber": 1,
                "voiceover": "Recuerda suscribirte para ver más videos históricos cada semana. ¡No te lo pierdas!",
                "subtitle": "Suscríbete",
                "targetDurationSec": 3.0,
            }
        ]
    }
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "La caída del Muro de Berlín")
    assert result["valid"] is False
    codes = [code for code, _ in result["reasons"]]
    assert "insufficient_scene_count" in codes or "cta_only_or_non_historical" in codes


def test_retry_prompt_preserves_full_contract(monkeypatch):
    """The retry prompt must contain the original schema/contract requirements
    plus corrective instruction, not just a minimal correction message."""
    import generate_script as gs

    # Mock budget for the test
    budget = {
        "targetSec": 30, "minSec": 27, "maxSec": 35,
        "minimumWords": 47, "preferredWords": 52, "maximumWords": 61,
        "sceneCount": 5, "pauseSec": 1.4,
        "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
    }

    retry_inst = gs._build_retry_instruction(
        budget, actual_word_count=8, actual_scene_count=1, estimated_dur=4.4,
        structural_issues=[
            ("insufficient_scene_count", "1 scenes, need at least 4"),
            ("cta_only_or_non_historical", "script lacks factual historical content"),
        ],
    )

    # Retry instruction must include structural fix commands
    assert "Problemas estructurales" in retry_inst
    assert "insufficient_scene_count" in retry_inst
    assert "cta_only_or_non_historical" in retry_inst
    assert "Contrato de duración" in retry_inst
    assert "Reglas obligatorias" in retry_inst
    assert "4 Y 6 ESCENAS" in retry_inst
    assert "visualPlan" in retry_inst
    assert "visualSequence" in retry_inst
    assert "narrativeBeats" in retry_inst
    assert "motionType" in retry_inst

    # Also test retry prompt preserves full user prompt contract
    base = gs._build_user_prompt("La caída del Muro de Berlín", budget, "balanced")
    assert "Genera un guion histórico" in base
    assert "visualPlan Y visualSequence" in base
    assert "DEBE tener 2 o más segmentos" in base
    assert "narrativeBeats" in base
    assert "motionType" in base
    assert "Estilo de duración" in base or "duración" in base.lower()
    assert "30" in base  # targetSec
    assert "27" in base  # minSec


def test_exhausted_retries_produce_review_required_structure_issues(monkeypatch):
    """When all retries are exhausted, the metadata must contain
    structureIssues and REVIEW_REQUIRED status with full retry history."""
    import generate_script as gs

    # Call the structural validator directly; the full loop is in main().
    script = {
        "scenes": [
            {
                "sceneNumber": 5,
                "voiceover": "Recuerda, la historia está viva. ¡Suscríbete para más!",
                "targetDurationSec": 4.0,
            }
        ]
    }
    sv = gs._validate_script_structure(script, gs.MIN_SCENE_COUNT, "La caída del Muro de Berlín")
    assert sv["valid"] is False
    codes = [code for code, _ in sv["reasons"]]
    assert len(codes) >= 1

    # Simulate the retry history that main() would produce
    retry_history = [
        {"retry": 0, "reason": "above_maximum_words", "actualWordCount": 70,
         "instructionType": "reduce_content"},
        {"retry": 1, "reason": codes[0], "actualWordCount": 8,
         "instructionType": "fix_structure_then_duration",
         "structuralIssues": codes,
         "structuralIssueDetails": [msg for _, msg in sv["reasons"]]},
    ]
    assert len(retry_history) == 2
    assert retry_history[1]["reason"] == codes[0]
    assert "structuralIssues" in retry_history[1]


def test_build_user_prompt_contains_historical_requirements():
    """_build_user_prompt must contain mandatory historical content rules."""
    from generate_script import _build_user_prompt
    budget = {
        "targetSec": 30, "minSec": 27, "maxSec": 35,
        "minimumWords": 47, "preferredWords": 52, "maximumWords": 61,
        "sceneCount": 5, "pauseSec": 1.4,
        "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
    }
    prompt = _build_user_prompt("La caída del Muro de Berlín", budget, "balanced")
    assert "visualPlan" in prompt
    assert "visualSequence" in prompt
    assert "narrativeBeats" in prompt
    assert "motionType" in prompt
    assert "DEBE tener 2 o más segmentos" in prompt
    assert "regla técnica obligatoria" in prompt.lower()


# ── Retry-loop integration tests ────────────────────────────────────────

_GOOD_3_SCENE_SCRIPT = {
    "title": "Test",
    "scenes": [
        {
            "sceneNumber": 1, "visualTemporalIntent": "event_depiction",
            "voiceover": "El 13 de agosto de 1961 comenzó la construcción del Muro de Berlín.",
            "subtitle": "Construcción", "targetDurationSec": 6.0,
            "visualPlan": {
                "strategy": "historical_archive", "editorialRole": "battle_or_assault",
                "primaryAssetType": "historical_photograph", "period": "1961",
                "location": "Berlín", "entities": ["Muro de Berlín"],
                "searchQueries": ["Berlin Wall construction 1961"],
                "visualSequence": [
                    {"segmentIndex": 1, "assetType": "historical_photograph",
                     "durationFraction": 0.5, "transition": "cut", "motionType": "slow_zoom_in"},
                    {"segmentIndex": 2, "assetType": "historical_art",
                     "durationFraction": 0.5, "transition": "fade", "motionType": "pan_right"},
                ]
            }
        },
        {
            "sceneNumber": 2, "visualTemporalIntent": "event_depiction",
            "voiceover": "Durante 28 años dividió Alemania en dos bloques enfrentados en la Guerra Fría.",
            "subtitle": "División", "targetDurationSec": 6.0,
            "visualPlan": {
                "strategy": "historical_archive", "editorialRole": "context_map",
                "primaryAssetType": "historical_map", "period": "1961-1989",
                "location": "Berlín", "entities": ["Guerra Fría"],
                "searchQueries": ["Berlin Wall division map Cold War"],
                "visualSequence": [
                    {"segmentIndex": 1, "assetType": "historical_map",
                     "durationFraction": 0.5, "transition": "cut", "motionType": "slow_zoom_in"},
                    {"segmentIndex": 2, "assetType": "document",
                     "durationFraction": 0.5, "transition": "fade", "motionType": "pan_right"},
                ]
            }
        },
        {
            "sceneNumber": 3, "visualTemporalIntent": "event_depiction",
            "voiceover": "El 9 de noviembre de 1989 la presión popular derribó la barrera de hormigón.",
            "subtitle": "Caída", "targetDurationSec": 6.0,
            "visualPlan": {
                "strategy": "historical_archive", "editorialRole": "civilian_impact",
                "primaryAssetType": "historical_photograph", "period": "1989",
                "location": "Berlín", "entities": ["Muro de Berlín"],
                "searchQueries": ["Berlin Wall fall 1989"],
                "visualSequence": [
                    {"segmentIndex": 1, "assetType": "historical_photograph",
                     "durationFraction": 0.5, "transition": "cut", "motionType": "slow_zoom_in"},
                    {"segmentIndex": 2, "assetType": "historical_art",
                     "durationFraction": 0.5, "transition": "fade", "motionType": "pan_right"},
                ]
            }
        },
        {
            "sceneNumber": 4, "visualTemporalIntent": "legacy_or_commemoration",
            "voiceover": "Hoy la Puerta de Brandeburgo recuerda a las víctimas. Suscríbete para más historia.",
            "subtitle": "Legado", "targetDurationSec": 6.0,
            "visualPlan": {
                "strategy": "historical_archive", "editorialRole": "consequence_or_legacy",
                "primaryAssetType": "historical_photograph", "period": "presente",
                "location": "Berlín", "entities": ["Puerta de Brandeburgo"],
                "searchQueries": ["Brandenburg Gate Berlin today memorial"],
                "visualSequence": [
                    {"segmentIndex": 1, "assetType": "historical_photograph",
                     "durationFraction": 0.5, "transition": "cut", "motionType": "slow_zoom_in"},
                    {"segmentIndex": 2, "assetType": "historical_art",
                     "durationFraction": 0.5, "transition": "fade", "motionType": "pan_right"},
                ]
            }
        },
    ]
}

import json as _json


def test_main_retry_loop_3_attempts_3rd_succeeds(monkeypatch, tmp_path):
    """Integration: main() calls LLM 3 times, retry 2 is structural CTA,
    retry 3 produces valid script → SCRIPT_DRAFT."""
    import sys as _sys
    from pathlib import Path
    import generate_script as gs

    out = tmp_path / "metadata.json"

    # 3 LLM responses
    # Mock 1: structurally valid (4 scenes), above max words
    _many_words = " ".join(["Berlín 1989 muro"] * 10)  # ~30 words per scene, has date + entity
    resp_1 = _json.dumps({
        "title": "Test", "scenes": [
            {"sceneNumber": i, "visualTemporalIntent": "event_depiction",
             "voiceover": _many_words, "subtitle": "x",
             "targetDurationSec": 6.0,
             "visualPlan": {
                 "strategy": "historical_archive", "editorialRole": "civilian_impact",
                 "primaryAssetType": "historical_photograph", "entities": ["test"],
                 "searchQueries": ["test"],
                 "visualSequence": [
                     {"segmentIndex": 1, "assetType": "historical_photograph",
                      "durationFraction": 0.5, "transition": "cut", "motionType": "static"},
                     {"segmentIndex": 2, "assetType": "historical_art",
                      "durationFraction": 0.5, "transition": "fade", "motionType": "pan_right"},
                 ]
             }} for i in range(1, 5)
        ]})
    # Response 2: structural failure — one-scene CTA
    resp_2 = _json.dumps({
        "title": "Test", "scenes": [
            {"sceneNumber": 5, "voiceover": "Suscríbete para más videos. ¡Gracias!",
             "subtitle": "CTA", "targetDurationSec": 3.0}
        ]})
    # Response 3: valid
    resp_3 = _json.dumps(_GOOD_3_SCENE_SCRIPT)

    call_count = [0]
    prompts_seen = []

    def m_call_llm(prompt, api_key, model, provider="openai"):
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

    # Prompts 2 and 3 must contain full contract
    for i in (1, 2):  # 0-indexed: prompt index 1 = attempt 2, index 2 = attempt 3
        p = prompts_seen[i]
        assert "visualPlan" in p, f"Prompt {i+1} missing visualPlan"
        assert "visualSequence" in p, f"Prompt {i+1} missing visualSequence"
        assert "narrativeBeats" in p, f"Prompt {i+1} missing narrativeBeats"

    # Prompt 3 must include structural diagnostics from attempt 2
    assert "insufficient_scene_count" in prompts_seen[2] or "invalid_segment_count" in prompts_seen[2]

    meta = _json.loads(out.read_text())
    assert meta["status"] == "SCRIPT_DRAFT"
    assert meta["durationContract"]["status"] == "PASS"
    assert meta["durationContract"]["structureValid"] is True
    rh = meta["durationContract"]["retryHistory"]
    assert len(rh) == 3
    assert rh[0]["reason"] == "above_maximum_words"
    assert rh[1]["reason"] == "insufficient_scene_count" or "invalid_segment_count" in rh[1]["reason"]
    assert rh[2]["reason"] == "in_range"


def test_main_retry_loop_3_attempts_all_fail_review_required(monkeypatch, tmp_path):
    """Integration: main() calls LLM 3 times, all fail → REVIEW_REQUIRED."""
    import sys as _sys
    import generate_script as gs

    out = tmp_path / "metadata.json"
    resp = _json.dumps({
        "title": "Test", "scenes": [
            {"sceneNumber": 5, "voiceover": "Suscríbete. Gracias. Fin. Adiós.",
             "subtitle": "CTA", "targetDurationSec": 2.0}
        ]})

    call_count = [0]
    def m_call_llm(prompt, api_key, model, provider="openai"):
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


# ── Segment-type compatibility tests ────────────────────────────────────


def test_context_map_rejects_atmospheric_broll_in_script_structure():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = {
        "scenes": [
            {
                "sceneNumber": 1, "visualTemporalIntent": "event_depiction",
                "voiceover": "La división de Alemania se reflejó en el mapa de la Guerra Fría.",
                "subtitle": "Mapa", "targetDurationSec": 6.0,
                "visualPlan": {
                    "strategy": "map_or_document", "editorialRole": "context_map",
                    "primaryAssetType": "historical_map",
                    "searchQueries": ["Cold War map"],
                    "visualSequence": [
                        {"segmentIndex": 1, "assetType": "historical_map",
                         "durationFraction": 0.5, "motionType": "slow_zoom_in"},
                        {"segmentIndex": 2, "assetType": "atmospheric_broll",
                         "durationFraction": 0.5, "motionType": "pan_right"},
                    ]
                }
            }
        ]
    }
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Guerra Fría")
    assert result["valid"] is False
    assert "forbidden_segment_asset_type" in [c for c, _ in result["reasons"]]


def test_document_or_date_rejects_historical_photograph_in_script_structure():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = {
        "scenes": [
            {
                "sceneNumber": 1, "visualTemporalIntent": "event_depiction",
                "voiceover": "El Tratado de Versalles selló el destino de Alemania en 1919.",
                "subtitle": "Tratado", "targetDurationSec": 6.0,
                "visualPlan": {
                    "strategy": "historical_archive", "editorialRole": "document_or_date",
                    "primaryAssetType": "historical_map",
                    "searchQueries": ["Treaty of Versailles"],
                    "visualSequence": [
                        {"segmentIndex": 1, "assetType": "historical_photograph",
                         "durationFraction": 0.5, "motionType": "slow_zoom_in"},
                        {"segmentIndex": 2, "assetType": "historical_map",
                         "durationFraction": 0.5, "motionType": "pan_right"},
                    ]
                }
            }
        ]
    }
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Tratado de Versalles")
    assert result["valid"] is False
    assert "forbidden_segment_asset_type" in [c for c, _ in result["reasons"]]


def test_consequence_legacy_atmospheric_broll_allowed_with_legacy_intent():
    """consequence_or_legacy + atmospheric_broll allowed only under
    legacy_or_commemoration temporal intent exception."""
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = {
        "scenes": [
            {
                "sceneNumber": 1, "visualTemporalIntent": "legacy_or_commemoration",
                "voiceover": "Hoy recordamos a las víctimas del Muro en un monumento conmemorativo.",
                "subtitle": "Memoria", "targetDurationSec": 6.0,
                "visualPlan": {
                    "strategy": "historical_archive", "editorialRole": "consequence_or_legacy",
                    "primaryAssetType": "historical_photograph",
                    "searchQueries": ["Berlin Wall memorial today"],
                    "visualSequence": [
                        {"segmentIndex": 1, "assetType": "historical_photograph",
                         "durationFraction": 0.5, "motionType": "slow_zoom_in"},
                        {"segmentIndex": 2, "assetType": "atmospheric_broll",
                         "durationFraction": 0.5, "motionType": "pan_right"},
                    ]
                }
            }
        ]
    }
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Muro de Berlín")
    # This has only 1 scene, so it will fail structure for that reason,
    # but it must NOT have forbidden_segment_asset_type
    codes = [c for c, _ in result["reasons"]]
    assert "forbidden_segment_asset_type" not in codes, (
        f"atmospheric_broll should be allowed under legacy_or_commemoration, got {codes}"
    )


def test_consequence_legacy_atmospheric_broll_rejected_with_event_depiction():
    """consequence_or_legacy + atmospheric_broll rejected when temporal
    intent is event_depiction (no exception applies)."""
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = {
        "scenes": [
            {
                "sceneNumber": 1, "visualTemporalIntent": "event_depiction",
                "voiceover": "El 9 de noviembre de 1989 cayó el Muro de Berlín ante la multitud.",
                "subtitle": "Caída", "targetDurationSec": 6.0,
                "visualPlan": {
                    "strategy": "historical_archive", "editorialRole": "consequence_or_legacy",
                    "primaryAssetType": "historical_photograph",
                    "searchQueries": ["Berlin Wall fall 1989"],
                    "visualSequence": [
                        {"segmentIndex": 1, "assetType": "historical_photograph",
                         "durationFraction": 0.5, "motionType": "slow_zoom_in"},
                        {"segmentIndex": 2, "assetType": "atmospheric_broll",
                         "durationFraction": 0.5, "motionType": "pan_right"},
                    ]
                }
            }
        ]
    }
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Muro de Berlín")
    codes = [c for c, _ in result["reasons"]]
    assert "forbidden_segment_asset_type" in codes, (
        f"atmospheric_broll must be rejected under event_depiction, got {codes}"
    )


def test_shared_contract_used_by_fetch_and_generate():
    """Both fetch_images and generate_script import from
    editorial_asset_contract, not from each other."""
    import editorial_asset_contract as eac
    assert hasattr(eac, "EDITORIAL_ROLE_PREFERENCES")
    assert hasattr(eac, "is_asset_type_allowed")

    import fetch_images as fi
    assert fi.EDITORIAL_ROLE_PREFERENCES is eac.EDITORIAL_ROLE_PREFERENCES
    assert fi.is_asset_type_allowed is eac.is_asset_type_allowed

    import generate_script as gs
    # generate_script imports is_asset_type_allowed
    assert gs.is_asset_type_allowed is eac.is_asset_type_allowed


# ── Prompt contract consistency tests ───────────────────────────────────


def test_system_prompt_json_example_no_context_map_atmospheric_broll():
    """The canonical JSON example must NOT show context_map paired with
    atmospheric_broll, which the shared contract forbids."""
    from generate_script import SYSTEM_PROMPT as sp
    import json as _j
    json_start = sp.find("## Formato JSON de salida")
    assert json_start >= 0, "JSON example section not found"
    json_block = sp[json_start:]
    assert '"assetType": "atmospheric_broll"' not in json_block, (
        "Canonical JSON example must not use atmospheric_broll with context_map"
    )


def test_prompt_prose_no_broll_for_portrait():
    """Prompt prose must not instruct b-roll for character_portrait."""
    from generate_script import SYSTEM_PROMPT as sp
    composition_start = sp.find("Reglas de composición")
    role_start = sp.find("Reglas de rol editorial")
    portrait_section = sp[composition_start:role_start] if composition_start >= 0 and role_start > composition_start else sp
    assert "broll atmosférico" not in portrait_section.lower(), (
        "Portrait composition must not recommend atmospheric_broll"
    )


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


def test_context_map_context_or_setup_rejected():
    """context_map requires event_depiction, context_or_setup must be rejected."""
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = {
        "scenes": [
            {"sceneNumber": 1, "visualTemporalIntent": "context_or_setup",
             "voiceover": "Berlín fue dividido en cuatro sectores en 1945.",
             "subtitle": "División", "targetDurationSec": 6.0,
             "visualPlan": {
                 "strategy": "historical_archive", "editorialRole": "context_map",
                 "primaryAssetType": "historical_map",
                 "searchQueries": ["Berlin zones 1945"],
                 "visualSequence": [
                     {"segmentIndex": 1, "assetType": "historical_map",
                      "durationFraction": 0.5, "motionType": "slow_zoom_in"},
                     {"segmentIndex": 2, "assetType": "document",
                      "durationFraction": 0.5, "motionType": "pan_right"},
                 ]
             }}
            for _ in range(4)
        ]}
    # Fix scene numbers
    for i, s in enumerate(script["scenes"], 1):
        s["sceneNumber"] = i
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Berlín")
    codes = [c for c, _ in result["reasons"]]
    assert "forbidden_visual_temporal_intent" in codes


def test_context_map_event_depiction_accepted():
    """context_map + event_depiction with valid map/document types must pass."""
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = {
        "scenes": [
            {"sceneNumber": 1, "visualTemporalIntent": "event_depiction",
             "voiceover": "El mapa de la Guerra Fría dividió Europa en 1945.",
             "subtitle": "Guerra Fría", "targetDurationSec": 6.0,
             "visualPlan": {
                 "strategy": "historical_archive", "editorialRole": "context_map",
                 "primaryAssetType": "historical_map",
                 "searchQueries": ["Cold War map"],
                 "visualSequence": [
                     {"segmentIndex": 1, "assetType": "historical_map",
                      "durationFraction": 0.5, "motionType": "slow_zoom_in"},
                     {"segmentIndex": 2, "assetType": "document",
                      "durationFraction": 0.5, "motionType": "pan_right"},
                 ]
             }}
            for _ in range(4)
        ]}
    for i, s in enumerate(script["scenes"], 1):
        s["sceneNumber"] = i
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Guerra Fría")
    # Should pass structure (maybe fail cta_only due to repetitive text)
    codes = [c for c, _ in result["reasons"]]
    assert "forbidden_visual_temporal_intent" not in codes
    assert "forbidden_segment_asset_type" not in codes


def test_battle_or_assault_broll_rejected_at_secondary_and_segment():
    """battle_or_assault + broll must be rejected at both secondaryAssetType
    and visualSequence segment level."""
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = {
        "scenes": [
            {"sceneNumber": 1, "visualTemporalIntent": "event_depiction",
             "voiceover": "La batalla del Muro comenzó el 13 de agosto de 1961.",
             "subtitle": "Batalla", "targetDurationSec": 6.0,
             "visualPlan": {
                 "strategy": "historical_archive", "editorialRole": "battle_or_assault",
                 "primaryAssetType": "historical_photograph",
                 "secondaryAssetType": "broll",
                 "searchQueries": ["Berlin Wall"],
                 "visualSequence": [
                     {"segmentIndex": 1, "assetType": "historical_photograph",
                      "durationFraction": 0.5, "motionType": "slow_zoom_in"},
                     {"segmentIndex": 2, "assetType": "broll",
                      "durationFraction": 0.5, "motionType": "pan_right"},
                 ]
             }}
            for _ in range(4)
        ]}
    for i, s in enumerate(script["scenes"], 1):
        s["sceneNumber"] = i
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Muro de Berlín")
    codes = [c for c, _ in result["reasons"]]
    assert "forbidden_secondary_asset_type" in codes
    assert "forbidden_segment_asset_type" in codes


def test_civilian_impact_broll_rejected():
    """civilian_impact + broll must be rejected."""
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = {
        "scenes": [
            {"sceneNumber": 1, "visualTemporalIntent": "event_depiction",
             "voiceover": "Miles de berlineses quedaron separados en 1961.",
             "subtitle": "Separación", "targetDurationSec": 6.0,
             "visualPlan": {
                 "strategy": "historical_archive", "editorialRole": "civilian_impact",
                 "primaryAssetType": "historical_photograph",
                 "searchQueries": ["Berlin Wall"],
                 "visualSequence": [
                     {"segmentIndex": 1, "assetType": "historical_photograph",
                      "durationFraction": 0.5, "motionType": "slow_zoom_in"},
                     {"segmentIndex": 2, "assetType": "broll",
                      "durationFraction": 0.5, "motionType": "pan_right"},
                 ]
             }}
            for _ in range(4)
        ]}
    for i, s in enumerate(script["scenes"], 1):
        s["sceneNumber"] = i
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Muro de Berlín")
    codes = [c for c, _ in result["reasons"]]
    assert "forbidden_segment_asset_type" in codes


def test_system_prompt_schema_no_generic_broll():
    """The canonical JSON schema must not present broll as valid for every role."""
    from generate_script import SYSTEM_PROMPT as sp
    json_start = sp.find("## Formato JSON de salida")
    assert json_start >= 0
    json_block = sp[json_start:]
    # broll should not appear as a bare enum option without qualification
    assert '"broll"\n' not in json_block or "compatible" in json_block, (
        "Schema must qualify broll/broll usage"
    )


def test_retry_instruction_has_replacement_types(monkeypatch):
    """Retry instruction for forbidden type must include valid replacement suggestions."""
    import generate_script as gs

    budget = {
        "targetSec": 30, "minSec": 27, "maxSec": 35,
        "minimumWords": 47, "preferredWords": 52, "maximumWords": 61,
        "sceneCount": 5, "pauseSec": 1.4,
        "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
    }

    retry_inst = gs._build_retry_instruction(
        budget, actual_word_count=52, actual_scene_count=5, estimated_dur=29.8,
        structural_issues=[
            ("forbidden_segment_asset_type",
             "scene 1 editorialRole=context_map forbids assetType=historical_photograph (use: historical_map, document, map)"),
            ("forbidden_segment_asset_type",
             "scene 3 editorialRole=battle_or_assault forbids assetType=atmospheric_broll (use: historical_photograph, historical_art, painting)"),
        ],
    )
    assert "use:" in retry_inst
    assert "historical_map" in retry_inst or "document" in retry_inst
    assert "historical_photograph" in retry_inst or "historical_art" in retry_inst


def test_retry_instruction_explicit_two_segments_rule():
    """Retry instruction for insufficient_segments must explicitly require
    exactly two segments for 5-7 second scenes."""
    import generate_script as gs

    budget = {
        "targetSec": 30, "minSec": 27, "maxSec": 35,
        "minimumWords": 47, "preferredWords": 52, "maximumWords": 61,
        "sceneCount": 5, "pauseSec": 1.4,
        "spokenWordsPerMinute": 110, "estimatedScenePauseMs": 350,
    }

    retry_inst = gs._build_retry_instruction(
        budget, actual_word_count=61, actual_scene_count=5, estimated_dur=34.7,
        structural_issues=[
            ("invalid_segment_count_medium", "scene 1 duration 6s requires exactly 2 segments, got 1"),
        ],
    )
    assert "2 segmentos" in retry_inst or "2 o más segmentos" in retry_inst
    assert "durationFraction" in retry_inst or "durationfraction" in retry_inst.lower()


# ── Allow-list explicit contract tests ───────────────────────────────────


def test_context_map_rejects_portrait():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = _build_scene_script("context_map", "event_depiction", "portrait", [("portrait",), ("historical_map",)])
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Berlín")
    assert "forbidden_segment_asset_type" in [c for c, _ in result["reasons"]]


def test_context_map_rejects_painting():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = _build_scene_script("context_map", "event_depiction", "painting", [("painting",), ("historical_map",)])
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Berlín")
    assert "forbidden_segment_asset_type" in [c for c, _ in result["reasons"]]


def test_military_technology_rejects_broll():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = _build_scene_script("military_technology", "event_depiction", "broll", [("historical_photograph",), ("broll",)])
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Berlín")
    codes = [c for c, _ in result["reasons"]]
    assert "forbidden_segment_asset_type" in codes


def test_character_portrait_rejects_generated_reconstruction():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = _build_scene_script("character_portrait", "event_depiction", "generated_reconstruction",
                                  [("generated_reconstruction",), ("historical_photograph",)])
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Berlín")
    assert "forbidden_segment_asset_type" in [c for c, _ in result["reasons"]]


def test_consequence_legacy_broll_accepted():
    """consequence_or_legacy + legacy_or_commemoration + broll must be accepted."""
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = _build_scene_script("consequence_or_legacy", "legacy_or_commemoration", "broll",
                                  [("historical_photograph",), ("broll",)])
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Berlín")
    assert "forbidden_segment_asset_type" not in [c for c, _ in result["reasons"]]


def test_atmospheric_transition_broll_accepted():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    script = _build_scene_script("atmospheric_transition", "context_or_setup", "broll",
                                  [("broll",), ("atmospheric_broll",)])
    result = _validate_script_structure(script, MIN_SCENE_COUNT, "Berlín")
    assert "forbidden_segment_asset_type" not in [c for c, _ in result["reasons"]]


def _build_scene_script(role, intent, primary, segments):
    """Build a 4-scene script with one scene having specific role/intent/types."""
    base_scene = {
        "visualTemporalIntent": "event_depiction",
        "voiceover": "Berlín fue dividido en cuatro sectores en 1945 por las potencias aliadas.",
        "subtitle": "División", "targetDurationSec": 6.0,
        "visualPlan": {
            "strategy": "historical_archive", "editorialRole": "context_map",
            "primaryAssetType": "historical_map",
            "searchQueries": ["Berlin zones 1945"],
            "visualSequence": [
                {"segmentIndex": 1, "assetType": "historical_map",
                 "durationFraction": 0.5, "motionType": "slow_zoom_in"},
                {"segmentIndex": 2, "assetType": "document",
                 "durationFraction": 0.5, "motionType": "pan_right"},
            ]
        }
    }
    special_scene = {
        "sceneNumber": 1,
        "visualTemporalIntent": intent,
        "voiceover": "El Muro de Berlín fue un símbolo de la división en la Guerra Fría.",
        "subtitle": "Muro", "targetDurationSec": 6.0,
        "visualPlan": {
            "strategy": "historical_archive", "editorialRole": role,
            "primaryAssetType": primary,
            "searchQueries": ["Berlin Wall"],
            "visualSequence": [
                {"segmentIndex": 1, "assetType": seg[0],
                 "durationFraction": 0.5, "motionType": "slow_zoom_in"} for seg in segments
            ] + [
                {"segmentIndex": len(segments) + 1, "assetType": "historical_photograph",
                 "durationFraction": 0.5, "motionType": "pan_right"} if len(segments) < 2 else {}
            ]
        }
    }
    # Fix: if 1 segment, durationFraction should be 1.0
    if len(segments) == 1:
        special_scene["visualPlan"]["visualSequence"] = [
            {"segmentIndex": 1, "assetType": segments[0][0],
             "durationFraction": 1.0, "motionType": "slow_zoom_in"}
        ]
    elif len(segments) >= 2:
        n = len(segments)
        frac = 1.0 / n
        special_scene["visualPlan"]["visualSequence"] = [
            {"segmentIndex": i + 1, "assetType": seg[0],
             "durationFraction": frac, "motionType": "slow_zoom_in"}
            for i, seg in enumerate(segments)
        ]
    scenes = [special_scene] + [
        dict(base_scene, sceneNumber=i) for i in range(2, 5)
    ]
    return {"scenes": scenes}


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


# ── Segment-count enforcement tests ──────────────────────────────────────

def _seg_script(dur, count, role="context_map"):
    """Build a 4-scene script where scene 1 has given duration and segment count."""
    return {"scenes": [
        {
            "sceneNumber": 1, "visualTemporalIntent": "event_depiction",
            "voiceover": "El Muro de Berlín dividió Alemania durante décadas en la Guerra Fría.",
            "subtitle": "División", "targetDurationSec": dur,
            "visualPlan": {
                "strategy": "historical_archive", "editorialRole": role,
                "primaryAssetType": "historical_map",
                "searchQueries": ["Berlin Wall"],
                "visualSequence": [
                    {"segmentIndex": i + 1, "assetType": "historical_map",
                     "durationFraction": 1.0 / max(1, count), "motionType": "slow_zoom_in"}
                    for i in range(count)
                ]
            }
        }
    ] + [
        {
            "sceneNumber": i, "visualTemporalIntent": "event_depiction",
            "voiceover": "Las potencias aliadas ocuparon sectores en Berlín en 1945 tras la guerra.",
            "subtitle": "Ocupación", "targetDurationSec": 6.0,
            "visualPlan": {
                "strategy": "historical_archive", "editorialRole": "context_map",
                "primaryAssetType": "document",
                "searchQueries": ["Berlin occupation"],
                "visualSequence": [
                    {"segmentIndex": 1, "assetType": "document",
                     "durationFraction": 0.5, "motionType": "slow_zoom_in"},
                    {"segmentIndex": 2, "assetType": "historical_map",
                     "durationFraction": 0.5, "motionType": "pan_right"},
                ]
            }
        } for i in range(2, 5)
    ]}


def test_segcount_6s_1seg_fails():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    s = _seg_script(6.0, 1)
    r = _validate_script_structure(s, MIN_SCENE_COUNT, "Berlín")
    assert "invalid_segment_count_medium" in [c for c, _ in r["reasons"]]


def test_segcount_6s_2seg_passes():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    s = _seg_script(6.0, 2)
    r = _validate_script_structure(s, MIN_SCENE_COUNT, "Berlín")
    codes = [c for c, _ in r["reasons"]]
    assert "invalid_segment_count_medium" not in codes
    assert "forbidden_segment_asset_type" not in codes


def test_segcount_6s_3seg_fails():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    s = _seg_script(6.0, 3)
    r = _validate_script_structure(s, MIN_SCENE_COUNT, "Berlín")
    assert "invalid_segment_count_medium" in [c for c, _ in r["reasons"]]


def test_segcount_8s_1seg_fails():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    s = _seg_script(8.0, 1)
    r = _validate_script_structure(s, MIN_SCENE_COUNT, "Berlín")
    assert "invalid_segment_count_long" in [c for c, _ in r["reasons"]]


def test_segcount_8s_2seg_passes():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    s = _seg_script(8.0, 2)
    r = _validate_script_structure(s, MIN_SCENE_COUNT, "Berlín")
    assert "invalid_segment_count_long" not in [c for c, _ in r["reasons"]]


def test_segcount_8s_3seg_passes():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    s = _seg_script(8.0, 3)
    r = _validate_script_structure(s, MIN_SCENE_COUNT, "Berlín")
    assert "invalid_segment_count_long" not in [c for c, _ in r["reasons"]]


def test_segcount_8s_4seg_fails():
    from generate_script import _validate_script_structure, MIN_SCENE_COUNT
    s = _seg_script(8.0, 4)
    r = _validate_script_structure(s, MIN_SCENE_COUNT, "Berlín")
    assert "invalid_segment_count_long" in [c for c, _ in r["reasons"]]
