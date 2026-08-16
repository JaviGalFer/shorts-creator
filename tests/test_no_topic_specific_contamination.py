"""Regression tests for topic-specific sourcing contamination.

Verifies that no Berlin, Constantinople, Istanbul, or other topic-specific
hardcoded vocabulary remains in shorts_creator.validation.asset.py production lists.

Run: python3 -m pytest tests/test_no_topic_specific_contamination.py -v
"""

import re
import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))


# ── Prohibited topic-specific terms in production source ─────────────────

PROHIBITED_TERMS = [
    "berlin wall", "berliner mauer", "muro de berlín", "muro de berlin",
    "berliner mauer bau", "mauerbau",
    "sectors of berlin", "east berlin west berlin", "berlin sectors",
    "zones of berlin", "berlin zones",
    "fall of the berlin wall", "fall of the berlin",
    "juggling on the berlin wall", "atop the berlin wall",
    "checkpoint charlie",
    "berlin wall in",
    "la caída de constantinopla",
]


def test_no_prohibited_terms_in_bin_asset_validation_source():
    """src/shorts_creator/validation/asset.py must not contain prohibited topic-specific terms
    in production-level term lists."""
    content = (PROJECT / "src" / "shorts_creator" / "validation" / "asset.py").read_text()
    for term in PROHIBITED_TERMS:
        count = len(re.findall(re.escape(term), content, re.IGNORECASE))
        assert count == 0, (
            f"PROHIBITED: '{term}' found {count} time(s) in src/shorts_creator/validation/asset.py"
        )


# ── No theme constraints remain in shorts_creator.validation.asset ──────────────────────


def test_theme_constraints_empty():
    """THEME_CONSTRAINTS must be empty — no hardcoded themes."""
    from shorts_creator.validation.asset import THEME_CONSTRAINTS
    assert len(THEME_CONSTRAINTS) == 0, (
        f"THEME_CONSTRAINTS must be empty, got: {list(THEME_CONSTRAINTS.keys())}"
    )


def test_legacy_keywords_no_topic_specific():
    """LEGACY_KEYWORDS must not contain Istanbul/Estambul."""
    from shorts_creator.validation.asset import LEGACY_KEYWORDS
    assert "estambul" not in LEGACY_KEYWORDS and "Estambul" not in LEGACY_KEYWORDS, \
        f"LEGACY_KEYWORDS contains Istanbul-specific term"
    assert "istanbul" not in LEGACY_KEYWORDS, \
        f"LEGACY_KEYWORDS contains istanbul"


def test_modern_query_keywords_no_topic_specific():
    """MODERN_QUERY_KEYWORDS must not contain Istanbul/Estambul."""
    from shorts_creator.validation.asset import MODERN_QUERY_KEYWORDS
    for kw in MODERN_QUERY_KEYWORDS:
        assert kw.lower() not in ("istanbul", "estambul"), \
            f"MODERN_QUERY_KEYWORDS contains Istanbul-specific term: '{kw}'"
