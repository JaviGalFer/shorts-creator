import pytest

from shorts_creator.contracts.duration import calculate_word_budget, resolve_scene_plan
from shorts_creator.script import generator as script_generator
from shorts_creator.script.generator import _build_duration_prompt_instruction_v2, _build_retry_instruction_v2, _validate_and_canonicalize_script_v2


@pytest.mark.parametrize("target,preferred,minimum,maximum", [
    (30, 5, 4, 6), (37, 6, 5, 7), (45, 8, 7, 9), (60, 10, 9, 11),
])
def test_duration_derived_scene_plan(target, preferred, minimum, maximum):
    assert resolve_scene_plan(target) == {
        "targetSceneDurationSec": 6,
        "preferredSceneCount": preferred,
        "minSceneCount": minimum,
        "maxSceneCount": maximum,
    }


def _script(count):
    return {"title": "Test", "scenes": [{
        "sceneNumber": number,
        "voiceover": "uno dos tres cuatro cinco seis siete",
        "subtitle": "test",
        "targetDurationSec": 6,
        "visualPlan": {"_schemaVersion": 2, "visualIntent": "explain", "subjects": ["x"],
                       "searchQueries": ["x"], "assetPreferences": ["diagram"],
                       "visualSequence": [{"segmentIndex": 1, "assetPreference": "diagram", "durationFraction": 1.0, "transition": "cut"}]},
    } for number in range(1, count + 1)]}


@pytest.mark.parametrize("count,valid", [(5, False), (9, True), (10, True), (11, True), (12, False)])
def test_deep_60_validator_uses_request_scene_plan(count, valid):
    canonical, errors, _ = _validate_and_canonicalize_script_v2(
        _script(count), allow_generated_images=False, scene_plan=resolve_scene_plan(60),
    )
    assert (canonical is not None) is valid
    if not valid:
        assert any(e["code"] in {"INSUFFICIENT_SCENE_COUNT", "EXCESSIVE_SCENE_COUNT"} for e in errors)


def test_dynamic_prompt_and_budget_use_preferred_scene_count():
    plan = resolve_scene_plan(60)
    budget = calculate_word_budget(target_sec=60, min_sec=55, max_sec=65, scene_count=plan["preferredSceneCount"])
    budget.update(plan)
    prompt = _build_duration_prompt_instruction_v2(budget, "balanced")
    assert "entre 9 y 11" in prompt and "Prefiere 10 escenas" in prompt
    assert "~6s por escena" in prompt
    assert budget["sceneCount"] == 10


@pytest.mark.parametrize("target,required,forbidden", [(60, "ENTRE 9 Y 11", "ENTRE 4 Y 6"), (30, "ENTRE 4 Y 6", "ENTRE 9 Y 11")])
def test_retry_prompt_uses_dynamic_scene_plan(target, required, forbidden):
    plan = resolve_scene_plan(target)
    budget = calculate_word_budget(target_sec=target, min_sec=target - 3, max_sec=target + 3, scene_count=plan["preferredSceneCount"])
    budget.update(plan)
    prompt = _build_retry_instruction_v2(budget, 10, plan["preferredSceneCount"], 10.0, [], False)
    assert required in prompt
    assert forbidden not in prompt


def test_deep_60_repair_preserves_ten_scene_plan(monkeypatch):
    source = _script(10)
    payload = {"scenes": [{"sceneNumber": i, "voiceover": "nueva voz con siete palabras para escena"} for i in range(1, 11)]}
    monkeypatch.setattr(script_generator, "call_llm", lambda *args, **kwargs: __import__("json").dumps(payload))
    repaired, errors = script_generator.repair_voiceover_duration(
        source, direction="EXPAND", target_total_words=80, scene_word_targets=[8] * 10,
        api_key="test", model="test", scene_plan=resolve_scene_plan(60),
    )
    assert errors == []
    assert [scene["sceneNumber"] for scene in repaired["scenes"]] == list(range(1, 11))


def test_minimum_supported_scene_plan_is_coherent():
    plan = resolve_scene_plan(20)
    assert plan["preferredSceneCount"] >= plan["minSceneCount"]
    assert plan == {"targetSceneDurationSec": 6, "preferredSceneCount": 4, "minSceneCount": 4, "maxSceneCount": 5}
