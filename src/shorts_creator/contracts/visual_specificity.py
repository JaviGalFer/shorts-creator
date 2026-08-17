"""Conservative visual-query specificity assessment.

Checks whether a visual search query carries discriminative, retrievable
content instead of being an editorial/vague abstraction.  The guard is
conservative by design: it rejects *clearly* vague queries and never tries to
prove query quality.  Single-entity queries (``Smosh``, ``Minecraft``,
``Chernobyl``) remain valid.

Pure module: no I/O, no HTTP, no provider calls, no pipeline imports.
Provider-agnostic: no provider, platform or domain-specific vocabulary.

Validity rule per query:

    content = tokenize(query) - STOPWORDS        # GENERIC_FILLER already excluded by tokenize
    weak    = content ∩ WEAK_SUPPORT_TERMS
    anchors = content - weak

Reject (``VAGUE``) when:
    - anchors is empty (no discriminative content), or
    - len(weak) >= len(anchors) (editorial/qualifier terms dominate or tie).
Otherwise pass (``VALID``).
"""

from __future__ import annotations

from typing import Any

from shorts_creator.contracts.visual_terms import (
    STOPWORDS,
    WEAK_SUPPORT_TERMS,
    tokenize,
)

VALID = "VALID"
VAGUE = "VAGUE"

QUERY_NOT_SPECIFIC = "QUERY_NOT_SPECIFIC"
SEGMENT_QUERY_NOT_SPECIFIC = "SEGMENT_QUERY_NOT_SPECIFIC"

_REASON_NO_ANCHORS = (
    "query has no discriminative anchor terms; only weak/editorial or filler "
    "content remains"
)
_REASON_WEAK_DOMINANCE = (
    "weak/editorial terms dominate or tie the discriminative anchors"
)
_REASON_VALID = "query carries discriminative anchor terms"


def assess_query_specificity(query: Any) -> dict:
    """Assess a single visual search query.

    Returns:
        ``{"ok", "verdict", "reason", "contentTerms", "weakTerms", "anchorTerms"}``
        where ``verdict`` is ``VALID`` or ``VAGUE``.
    """
    if not isinstance(query, str):
        return {
            "ok": False,
            "verdict": VAGUE,
            "reason": "query is not a string",
            "contentTerms": [],
            "weakTerms": [],
            "anchorTerms": [],
        }

    content = {t for t in tokenize(query) if t not in STOPWORDS}
    weak = content & WEAK_SUPPORT_TERMS
    anchors = content - weak

    if not anchors:
        return {
            "ok": False,
            "verdict": VAGUE,
            "reason": _REASON_NO_ANCHORS,
            "contentTerms": sorted(content),
            "weakTerms": sorted(weak),
            "anchorTerms": [],
        }

    if len(weak) >= len(anchors):
        return {
            "ok": False,
            "verdict": VAGUE,
            "reason": _REASON_WEAK_DOMINANCE,
            "contentTerms": sorted(content),
            "weakTerms": sorted(weak),
            "anchorTerms": sorted(anchors),
        }

    return {
        "ok": True,
        "verdict": VALID,
        "reason": _REASON_VALID,
        "contentTerms": sorted(content),
        "weakTerms": sorted(weak),
        "anchorTerms": sorted(anchors),
    }


def assess_visual_plan_specificity(plan: Any) -> dict:
    """Assess every query in a VisualPlan v2 dict.

    Checks each non-empty ``searchQueries`` entry (code ``QUERY_NOT_SPECIFIC``)
    and each non-null ``visualSequence[].searchQuery`` (code
    ``SEGMENT_QUERY_NOT_SPECIFIC``).  Segment queries that are absent or null
    are skipped (optional by the v2 segment contract).

    Returns:
        ``{"ok", "errors", "checks"}`` where ``ok`` is True only when every
        present query is ``VALID`` and ``errors`` lists failed queries with
        ``{code, path, query, assessment}``.
    """
    errors: list[dict] = []
    checks: list[dict] = []

    if not isinstance(plan, dict):
        return {
            "ok": False,
            "errors": [{
                "code": "INVALID_INPUT",
                "path": "visualPlan",
                "query": None,
                "assessment": {"verdict": VAGUE, "reason": "plan is not a dict"},
            }],
            "checks": checks,
        }

    scene_queries = plan.get("searchQueries")
    if isinstance(scene_queries, list):
        for i, q in enumerate(scene_queries):
            if not isinstance(q, str) or not q.strip():
                continue
            assessment = assess_query_specificity(q)
            checks.append({
                "path": f"searchQueries[{i}]",
                "query": q,
                "assessment": assessment,
            })
            if not assessment["ok"]:
                errors.append({
                    "code": QUERY_NOT_SPECIFIC,
                    "path": f"searchQueries[{i}]",
                    "query": q,
                    "assessment": assessment,
                })

    segment_list = plan.get("visualSequence")
    if isinstance(segment_list, list):
        for i, seg in enumerate(segment_list):
            if not isinstance(seg, dict):
                continue
            sq = seg.get("searchQuery")
            if not isinstance(sq, str) or not sq.strip():
                continue
            assessment = assess_query_specificity(sq)
            checks.append({
                "path": f"visualSequence[{i}].searchQuery",
                "query": sq,
                "assessment": assessment,
            })
            if not assessment["ok"]:
                errors.append({
                    "code": SEGMENT_QUERY_NOT_SPECIFIC,
                    "path": f"visualSequence[{i}].searchQuery",
                    "query": sq,
                    "assessment": assessment,
                })

    return {"ok": not errors, "errors": errors, "checks": checks}