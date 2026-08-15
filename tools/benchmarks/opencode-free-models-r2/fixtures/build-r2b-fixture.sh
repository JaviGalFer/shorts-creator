#!/usr/bin/env bash
#
# Build a hermetic R2-B sandbox derived from the PRE-fix state of the real
# "harden V2 word-budget control" change (fix commit bafb2d5, pre-fix parent
# d62c76a).
#
# The sandbox exposes only the pure function contract (missing/incomplete
# `_compute_operational_word_target`) plus deterministic tests that must pass
# once implemented. The real post-fix solution (bafb2d5) is NEVER written into
# the sandbox, so the benchmarked model cannot copy it.
#
# Usage:
#   bash tools/benchmarks/opencode-free-models-r2/fixtures/build-r2b-fixture.sh \
#     /path/to/isolated/sandbox
#
# Requires git access to this repository. Produces:
#   <sandbox>/src/generate_script.py     (pre-fix, incomplete function)
#   <sandbox>/tests/test_operational_word_target.py
#   <sandbox>/tests/conftest.py
#   <sandbox>/src/__init__.py            (empty, makes package importable)
#   <sandbox>/.opencode/agents/benchmark-builder.md

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
BENCH="$REPO/tools/benchmarks/opencode-free-models-r2"
PRE_FIX_COMMIT="d62c76a"    # parent of bafb2d5 — function absent
SRC="bin/generate_script.py"

SANDBOX="${1:-}"
if [[ -z "$SANDBOX" ]]; then
  echo "usage: $0 /path/to/isolated/sandbox" >&2
  exit 2
fi

if [[ -e "$SANDBOX" ]]; then
  echo "error: target already exists: $SANDBOX" >&2
  exit 2
fi

mkdir -p "$SANDBOX/src" "$SANDBOX/tests" "$SANDBOX/.opencode/agents"

# Materialize the R2-B agent locally so the sandbox can run it without
# registering it in the project or globally.
cp "$BENCH/agents/benchmark-builder.agent.md" \
   "$SANDBOX/.opencode/agents/benchmark-builder.md"

# Pre-fix generate_script.py from the parent of the real fix, plus its
# sibling imports (duration_profiles, visual_plan_v2) so the module imports
# cleanly. These are read-only dependencies, not the fix target.
git -C "$REPO" show "$PRE_FIX_COMMIT:$SRC" > "$SANDBOX/src/generate_script.py"
git -C "$REPO" show "$PRE_FIX_COMMIT:bin/duration_profiles.py" > "$SANDBOX/src/duration_profiles.py"
git -C "$REPO" show "$PRE_FIX_COMMIT:bin/visual_plan_v2.py" > "$SANDBOX/src/visual_plan_v2.py"
: > "$SANDBOX/src/__init__.py"

# Deterministic test (subset that exercises the pure function only).
cat > "$SANDBOX/tests/test_operational_word_target.py" <<'PY'
"""Deterministic tests for _compute_operational_word_target.

Extracted from the real test suite (TestOperationalWordTarget). No LLM, no
network, no providers. Pure function coverage only.
"""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SRC))

import generate_script as gs


class TestOperationalWordTarget:
    def _target(self, min_w, pref_w, max_w):
        return gs._compute_operational_word_target(
            {"minimumWords": min_w, "preferredWords": pref_w, "maximumWords": max_w})

    def test_c1_canonical_cases(self):
        cases = [
            (47, 52, 52, 50),
            (47, 50, 52, 50),
            (47, 49, 52, 49),
            (52, 52, 52, 52),
        ]
        for min_w, pref_w, max_w, expected in cases:
            got = self._target(min_w, pref_w, max_w)
            assert got == expected
            assert min_w <= got <= max_w

    def test_c1_invalid_budget_defensive(self):
        assert self._target(52, 52, 47) == 0
        assert gs._compute_operational_word_target(
            {"minimumWords": 47, "preferredWords": 52, "maximumWords": 0}) == 0
PY

: > "$SANDBOX/tests/conftest.py"

echo "R2-B fixture created at: $SANDBOX"
echo "Baseline: expect test_c1_* to FAIL until _compute_operational_word_target is implemented."
