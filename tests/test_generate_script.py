import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parents[1] / "bin"
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))


import json as _json
import generate_script as cli
from shorts_creator.script import generator as gs


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


_v2_long_vo = " ".join(["concepto divulgativo explicativo"] * 4)
_V2_VALID_4_SCENE = {
    "title": "Test",
    "scenes": [_v2_scene(i, voiceover=_v2_long_vo) for i in range(1, 5)],
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
    from shorts_creator.script.generator import MAX_SCRIPT_ATTEMPTS
    assert MAX_SCRIPT_ATTEMPTS == 3, (
        f"Expected MAX_SCRIPT_ATTEMPTS=3 (initial + 2 retries), got {MAX_SCRIPT_ATTEMPTS}"
    )


def test_valid_over_budget_script_is_accepted_without_bootstrap_retry(monkeypatch, tmp_path):
    """A V2-valid 67-word candidate reaches audio; WPM is telemetry only."""
    import sys as _sys
    out = tmp_path / "metadata.json"

    # resp_1: full script of 67 words -> estimated ~37.9s, over bootstrap max.
    resp_1 = _json.dumps({
        "title": "Test",
        "scenes": [_v2_scene(i, voiceover=" ".join(f"w{i}_{j}" for j in range(1, n + 1)))
                   for i, n in enumerate([14, 14, 13, 13, 13], start=1)],
    })
    # resp_2: voiceover-only repair payload of 40 words (cap-valid, below min 47).
    resp_2 = _json.dumps({
        "scenes": [{"sceneNumber": i, "voiceover": " ".join(f"c{i}_{j}" for j in range(1, 9))}
                   for i in range(1, 6)]
    })  # 8 words/scene -> 40, within caps [11,11,10,10,10] but below min
    # resp_3: full script of 48 words (expansion after a below-min candidate).
    resp_3 = _json.dumps({
        "title": "Test",
        "scenes": [
            _v2_scene(i, voiceover=" ".join(f"e{i}_{j}" for j in range(1, n + 1)))
            for i, n in enumerate([10, 10, 10, 9, 9], start=1)
        ],
    })  # 48 words, within [47, 52] -> PASS

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

    exit_code = cli.main()
    assert exit_code == 0

    assert call_count[0] == 1

    meta = _json.loads(out.read_text())
    assert meta["status"] == "SCRIPT_DRAFT"
    assert meta["durationContract"]["status"] == "FAIL"
    assert meta["durationContract"]["authority"] == "bootstrap_estimate"
    assert meta["durationContract"]["blocking"] is False
    assert meta["durationContract"]["structureValid"] is True
    rh = meta["durationContract"]["retryHistory"]
    assert len(rh) == 1
    assert rh[0]["strategy"] == "initial"
    assert rh[0]["reason"] == "above_maximum_words"
    assert not any("DURATION_OUT_OF_RANGE" in r for r in meta.get("reviewReasons", []))


def test_main_retry_loop_3_attempts_all_fail_review_required(monkeypatch, tmp_path):
    """Integration: main() calls LLM 3 times, all fail V2 validation -> REVIEW_REQUIRED."""
    import sys as _sys
    out = tmp_path / "metadata.json"
    resp = _json.dumps(_V2_SINGLE_SCENE_CTA)

    call_count = [0]
    def m_call_llm(prompt, api_key, model, provider="openai", system_prompt=None):
        call_count[0] += 1
        return resp

    monkeypatch.setattr(gs, "call_llm", m_call_llm)
    monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake", "LLM_PROVIDER": "openai"})
    monkeypatch.setattr(_sys, "argv", ["generate_script.py", "--topic", "Test", "--duration", "30",
                                        "--output", str(out)])

    exit_code = cli.main()
    assert exit_code == 0

    assert call_count[0] == 3
    meta = _json.loads(out.read_text())
    assert meta["status"] == "REVIEW_REQUIRED"
    assert meta["durationContract"]["status"] == "FAIL"
    assert meta["durationContract"]["structureValid"] is False
    assert len(meta["durationContract"]["structureIssues"]) >= 1
    rh = meta["durationContract"]["retryHistory"]
    assert len(rh) == 3
    assert "structuralIssues" in rh[2]
