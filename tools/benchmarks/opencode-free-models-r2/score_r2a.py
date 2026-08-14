#!/usr/bin/env python3
"""Deterministic scorer for R2-A (replay read-only).

Parses `opencode run --format json` output (events.jsonl) using the shared
event parser and reports:

  - found              : a final assistant text containing a JSON object
  - schema_valid       : JSON matches the required structure
  - answer_correct     : keyed fields matching the R1-audited ground truth
  - evidence_valid     : evidence strings point into allowed files (bin/...)
  - scope_violations   : tools/files observed outside the allowlist
  - tool_use_count     : number of tool_use events
  - tokens             : summed step_finish tokens (input/output/reasoning/cache)

PASS requires ALL of: found, schema_valid, 6/6 objective fields correct,
evidence_valid, zero scope violations.

Usage:
  python3 score_r2a.py <events.jsonl> [--quiet]

Exit codes: 0 PASS, 1 FAIL, 2 no final answer.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import events as evp

ALLOWED_FILES = ("bin/run_job.py", "bin/generate_script.py")

# Ground truth audited against commit 6e9bed5 by R1 (report §8).
TRUTH = {
    "defaultVisualSchemaVersion": 1,
    "runnerExplicitlyRequestsV2": False,
    "defaultAssetStageScript": "fetch_images.py",
    "v2AssetSwitchCondition": True,
    "allV1MetadataRejected": False,
    "mixedSchemaErrorCode": "MIXED_VISUAL_PLAN_SCHEMA_VERSIONS",
}

# Required schema keys (objective fields + structural fields).
REQUIRED_KEYS = {
    "defaultVisualSchemaVersion", "runnerExplicitlyRequestsV2",
    "defaultAssetStageScript", "v2AssetSwitchCondition",
    "allV1MetadataRejected", "mixedSchemaErrorCode",
    "v1OnlySymbols", "v2OnlySymbols", "historicalProductWording",
    "minimumSafeV2OnlyRuntimePlan", "verifiedUncertainties",
    "filesRead", "scopeViolations",
}
OBJECTIVE_FIELDS = set(TRUTH.keys())


def check_schema(payload):
    if not isinstance(payload, dict):
        return False, "not an object"
    missing = REQUIRED_KEYS - set(payload.keys())
    if missing:
        return False, f"missing fields: {sorted(missing)}"
    if not isinstance(payload.get("v1OnlySymbols"), list):
        return False, "v1OnlySymbols not a list"
    if not isinstance(payload.get("v2OnlySymbols"), list):
        return False, "v2OnlySymbols not a list"
    return True, "ok"


def field_value(payload, key):
    node = payload.get(key)
    if isinstance(node, dict) and "value" in node:
        return node["value"]
    return node


def answer_correct(payload):
    correct = 0
    for key, truth in TRUTH.items():
        val = field_value(payload, key)
        if isinstance(truth, bool):
            if isinstance(val, bool) and val == truth:
                correct += 1
        elif isinstance(truth, (int, float)):
            if isinstance(val, str):
                try:
                    val = int(val)
                except (TypeError, ValueError):
                    val = None
            if val == truth:
                correct += 1
        elif isinstance(truth, str):
            if isinstance(val, str) and truth.lower() in val.lower():
                correct += 1
    return correct


def evidence_valid(payload):
    valid = 0
    total = 0
    def walk(node):
        nonlocal valid, total
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "evidence" and isinstance(v, str):
                    total += 1
                    if any(af in v for af in ALLOWED_FILES):
                        valid += 1
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(payload)
    return valid, total


def scope_violations(path, payload):
    viol = list(payload.get("scopeViolations") or [])
    for use in evp.tool_uses(path):
        tool = use.get("tool") or ""
        inp = use.get("input")
        # Detect file paths observed via read/grep/glob/list tools. For grep the
        # file is `include`; `path` is only the search root (repo), not a file.
        if tool in ("read", "grep", "glob", "list") and isinstance(inp, dict):
            fp = inp.get("filePath") or inp.get("include") or inp.get("path")
            if isinstance(fp, str) and not any(af in fp for af in ALLOWED_FILES):
                viol.append(f"{tool} outside allowlist: {fp}")
    return viol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("events")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    payload = evp.last_json_answer(args.events)
    if payload is None:
        if not args.quiet:
            print(json.dumps({"found": False, "pass": False,
                              "reason": "no final JSON answer in stream"}))
        sys.exit(2)

    schema_ok, schema_msg = check_schema(payload)
    ans = answer_correct(payload)
    ev_ok, ev_total = evidence_valid(payload)
    viol = scope_violations(args.events, payload)

    pass_all = bool(schema_ok and ans == len(TRUTH) and ev_total > 0
                    and ev_ok == ev_total and not viol)

    result = {
        "found": True,
        "pass": pass_all,
        "schema_valid": schema_ok,
        "schema_note": schema_msg,
        "answer_correct": f"{ans}/{len(TRUTH)}",
        "evidence_valid": f"{ev_ok}/{ev_total}",
        "scope_violations": viol,
        "tool_use_count": len(evp.tool_uses(args.events)),
        "tokens": evp.step_finish_tokens(args.events),
        "filesRead": payload.get("filesRead"),
    }
    if not args.quiet:
        print(json.dumps(result, indent=2))
    sys.exit(0 if pass_all else 1)


if __name__ == "__main__":
    main()
