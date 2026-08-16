import pytest

from shorts_creator.contracts.duration import calculate_word_budget, resolve_scene_plan
from shorts_creator.script.generator import _build_duration_prompt_instruction_v2, _validate_and_canonicalize_script_v2


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
