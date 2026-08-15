#!/usr/bin/env bash
#
# Build a read-only R2-A sandbox replaying R1's exact snapshot (commit
# 6e9bed5) so R2-A is directly comparable with R1. Only the two allowed files
# are materialized; nothing is executed or modified.
#
# Usage:
#   bash tools/benchmarks/opencode-free-models-r2/fixtures/build-r2a-fixture.sh \
#     /path/to/isolated/sandbox
#
# Produces:
#   <sandbox>/bin/run_job.py
#   <sandbox>/bin/generate_script.py
#   <sandbox>/.opencode/agents/benchmark-readonly.md
#
# These are the exact bytes R1 audited. The sandbox is read-only for the run.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
BENCH="$REPO/tools/benchmarks/opencode-free-models-r2"
R1_COMMIT="6e9bed5"

SANDBOX="${1:-}"
if [[ -z "$SANDBOX" ]]; then
  echo "usage: $0 /path/to/isolated/sandbox" >&2
  exit 2
fi
if [[ -e "$SANDBOX" ]]; then
  echo "error: target already exists: $SANDBOX" >&2
  exit 2
fi

mkdir -p "$SANDBOX/bin" "$SANDBOX/.opencode/agents"
git -C "$REPO" show "$R1_COMMIT:bin/run_job.py" > "$SANDBOX/bin/run_job.py"
git -C "$REPO" show "$R1_COMMIT:bin/generate_script.py" > "$SANDBOX/bin/generate_script.py"

# Materialize the R2-A agent locally so the sandbox can run it without
# registering it in the project or globally.
cp "$BENCH/agents/benchmark-readonly.agent.md" \
   "$SANDBOX/.opencode/agents/benchmark-readonly.md"

echo "R2-A fixture created at: $SANDBOX"
