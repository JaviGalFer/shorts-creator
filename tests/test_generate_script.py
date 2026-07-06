import pytest
import re
from pathlib import Path

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
