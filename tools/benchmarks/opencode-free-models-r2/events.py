#!/usr/bin/env python3
"""Shared event parser for `opencode run --format json` output.

Normalizes the current OpenCode JSONL stream into a small, stable view used by
both R2 scorers and the runner:

  - assistant text     : type == "text"        -> part.text
  - tool calls         : type == "tool_use"    -> part.tool + part.state.input
  - step tokens        : type == "step_finish" -> part.tokens
  - session id         : event.sessionID

Defensive compatibility with older/alternative field placements is kept when
cheap (e.g. event.content vs event.part.text), but the current format
(event.part.*) is authoritative.

No model is invoked here — this is pure stream parsing.
"""
import json

CURRENT_TEXT = "text"
CURRENT_TOOL = "tool_use"
CURRENT_STEP = "step_finish"


def iter_events(path):
    """Yield each parsed event dict from a JSONL file (skips malformed lines)."""
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield evt


def text_content(evt):
    """Return the assistant text of a text event, or None."""
    if evt.get("type") != CURRENT_TEXT:
        return None
    part = evt.get("part") or {}
    return part.get("text") or evt.get("text") or evt.get("content")


def last_json_answer(path):
    """Return (json_object, found). Uses the LAST non-empty text event that
    contains a valid JSON object (best-effort extraction)."""
    best = None
    for evt in iter_events(path):
        txt = text_content(evt)
        if not txt or not isinstance(txt, str):
            continue
        obj = _extract_json(txt)
        if obj is not None:
            best = obj
    return best


def _extract_json(text):
    """Extract a JSON object from text, trying full-parse then bracketed slice."""
    candidates = [text.strip()]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def tool_uses(path):
    """Return list of dicts: {tool, input} for every tool_use event."""
    uses = []
    for evt in iter_events(path):
        if evt.get("type") != CURRENT_TOOL:
            continue
        part = evt.get("part") or {}
        tool = part.get("tool") or evt.get("tool")
        state = part.get("state") or {}
        inp = state.get("input") if isinstance(state, dict) else None
        uses.append({"tool": tool, "input": inp})
    return uses


def step_finish_tokens(path):
    """Return summed token metrics from all step_finish events.

    Returns a dict with 0 defaults; keys that never appear stay 0 (never
    invented — a missing key is indistinguishable from a true zero, and OpenCode
    reports explicit zeros when present).
    """
    totals = {"input": 0, "output": 0, "reasoning": 0,
              "cache_read": 0, "cache_write": 0}
    seen = 0
    for evt in iter_events(path):
        if evt.get("type") != CURRENT_STEP:
            continue
        part = evt.get("part") or {}
        toks = part.get("tokens")
        if not isinstance(toks, dict):
            continue
        seen += 1
        cache = toks.get("cache") or {}
        totals["input"] += toks.get("input") or 0
        totals["output"] += toks.get("output") or 0
        totals["reasoning"] += toks.get("reasoning") or 0
        totals["cache_read"] += cache.get("read") or 0
        totals["cache_write"] += cache.get("write") or 0
    totals["step_finish_seen"] = seen
    return totals


def first_session_id(path):
    for evt in iter_events(path):
        sid = evt.get("sessionID")
        if sid:
            return sid
    return None


def capture_evidence(path):
    """Return dict describing whether the stream contains evidence to score.

    - has_text     : at least one assistant text event with content
    - has_step_end : at least one step_finish event with token data
    - complete     : both present (evidence considered complete for capture)
    """
    has_text = False
    has_step_end = False
    for evt in iter_events(path):
        if evt.get("type") == CURRENT_TEXT and text_content(evt):
            has_text = True
        elif evt.get("type") == CURRENT_STEP:
            part = evt.get("part") or {}
            if part.get("tokens"):
                has_step_end = True
    return {
        "has_text": has_text,
        "has_step_end": has_step_end,
        "complete": has_text and has_step_end,
    }
