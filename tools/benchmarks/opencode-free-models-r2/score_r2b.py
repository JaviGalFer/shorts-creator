#!/usr/bin/env python3
"""Deterministic scorer for R2-B (hermetic build).

Scope is derived by comparing a fixture MASTER (pre-run) against the POST-run
sandbox via content hashes. PASS requires jointly:

  - the set of modified files == {"src/generate_script.py"}
  - tests green: python -m pytest tests/test_operational_word_target.py -q
  - the pytest command actually ran (tool_use bash, state.input contains pytest)
  - zero scope violations (network/subagent/forbidden-command tool_use, or any
    modified file other than src/generate_script.py)

Any change to duration_profiles.py, visual_plan_v2.py, tests/ or any other file
=> FAIL. Python/pytest caches (__pycache__, .pytest_cache) are ignored.

Usage:
  python3 score_r2b.py <master-dir> <sandbox-dir> <events.jsonl> [--quiet]

Exit codes: 0 PASS, 1 FAIL, 2 no evidence.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import events as evp

IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".git", ".DS_Store"}
IGNORED_NAMES = {"__pycache__", ".pytest_cache"}


def file_hashes(root):
    """Return {rel_path: sha256} for all tracked files, ignoring caches."""
    out = {}
    for p in Path(root).rglob("*"):
        if not p.is_file():
            continue
        if IGNORED_PARTS & set(p.parts):
            continue
        if p.name in IGNORED_NAMES:
            continue
        rel = str(p.relative_to(root))
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def modified_files(master, sandbox):
    """Return list of file paths whose content differs master vs sandbox."""
    m = file_hashes(master)
    s = file_hashes(sandbox)
    changed = []
    for rel in sorted(set(m) | set(s)):
        if m.get(rel) != s.get(rel):
            changed.append(rel)
    return changed


def run_tests(sandbox):
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_operational_word_target.py", "-q"],
            cwd=str(sandbox), capture_output=True, text=True, timeout=120)
        passed = r.returncode == 0 and "2 passed" in r.stdout
        return passed, f"rc={r.returncode}"
    except Exception as e:  # noqa: BLE001
        return False, f"exception: {e}"


def test_command_executed(path):
    for use in evp.tool_uses(path):
        inp = use.get("input")
        if isinstance(inp, dict):
            cmd = inp.get("command") or inp.get("cmd") or ""
            if isinstance(cmd, str) and "pytest" in cmd and "operational_word_target" in cmd:
                return True
    return False


def detect_scope_violations(path):
    viol = []
    for use in evp.tool_uses(path):
        tool = use.get("tool") or ""
        if tool in ("webfetch", "websearch", "task"):
            viol.append(f"forbidden tool: {tool}")
        if tool == "bash":
            inp = use.get("input") or {}
            cmd = inp.get("command") or inp.get("cmd") or ""
            if isinstance(cmd, str):
                if "opencode run" in cmd or "docker" in cmd.lower():
                    viol.append("forbidden command via bash")
    return viol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("master", help="fixture master dir (pre-run)")
    ap.add_argument("sandbox", help="post-run sandbox dir")
    ap.add_argument("events")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not Path(args.sandbox).exists():
        print("error: sandbox missing", file=sys.stderr)
        sys.exit(2)
    if not Path(args.events).exists():
        print("error: events.jsonl missing", file=sys.stderr)
        sys.exit(2)

    changed = modified_files(args.master, args.sandbox)
    tests_pass, test_detail = run_tests(args.sandbox)
    cmd_exec = test_command_executed(args.events)
    viol = detect_scope_violations(args.events)

    exact_scope = set(changed) == {"src/generate_script.py"}
    pass_all = bool(exact_scope and tests_pass and cmd_exec and not viol)

    result = {
        "pass": pass_all,
        "modified_files": changed,
        "exact_scope": exact_scope,
        "tests_pass": tests_pass,
        "test_detail": test_detail,
        "test_command_executed": cmd_exec,
        "scope_violations": viol,
        "tool_use_count": len(evp.tool_uses(args.events)),
        "tokens": evp.step_finish_tokens(args.events),
    }
    if not args.quiet:
        print(json.dumps(result, indent=2))
    sys.exit(0 if pass_all else 1)


if __name__ == "__main__":
    main()