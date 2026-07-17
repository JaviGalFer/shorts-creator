#!/usr/bin/env bash

set -u

REPO="/home/javi/projects/shorts-creator"
PROMPT="/tmp/shorts-benchmark-r1.txt"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$HOME/opencode-benchmarks/shorts-free-r1-$STAMP"

mkdir -p "$OUT"

git -C "$REPO" rev-parse HEAD > "$OUT/commit.txt"
git -C "$REPO" status --short > "$OUT/git-status-before.txt"

(
  cd "$REPO" &&
  opencode stats --days 1 --models 20 --project ""
) > "$OUT/stats-before.txt" 2>&1

run_model() {
  local label="$1"
  local model="$2"
  local variant="$3"

  echo
  echo "=== $label | $model | variant=${variant:-default} ==="

  local args=(
    opencode run
    --dir "$REPO"
    --model "$model"
    --agent benchmark-readonly
    --format json
    --title "benchmark-r1-$label"
  )

  if [[ -n "$variant" ]]; then
    args+=(--variant "$variant")
  fi

  local started
  local finished
  local rc

  started="$(date +%s)"

  /usr/bin/time \
    -f "wall_seconds=%e\nuser_seconds=%U\nsystem_seconds=%S\nmax_rss_kb=%M" \
    -o "$OUT/$label.time.txt" \
    "${args[@]}" "$(cat "$PROMPT")" \
    > "$OUT/$label.events.jsonl" \
    2> "$OUT/$label.stderr.txt"

  rc=$?
  finished="$(date +%s)"

  printf '%s\n' "$rc" > "$OUT/$label.exit-code.txt"
  printf '%s\n' "$((finished - started))" > "$OUT/$label.elapsed-seconds.txt"

  echo "Exit code: $rc"
  echo "Elapsed: $((finished - started)) seconds"

  sleep 60
}

run_model "big-pickle" \
  "opencode/big-pickle" \
  ""

run_model "deepseek-v4-flash-free-low" \
  "opencode/deepseek-v4-flash-free" \
  "low"

run_model "hy3-free-low" \
  "opencode/hy3-free" \
  "low"

run_model "mimo-v2.5-free-low" \
  "opencode/mimo-v2.5-free" \
  "low"

run_model "nemotron-3-ultra-free-low" \
  "opencode/nemotron-3-ultra-free" \
  "low"

run_model "north-mini-code-free-none" \
  "opencode/north-mini-code-free" \
  "none"

(
  cd "$REPO" &&
  opencode stats --days 1 --models 20 --project ""
) > "$OUT/stats-after.txt" 2>&1

opencode session list -n 15 --format json \
  > "$OUT/sessions-after.json" 2>&1

git -C "$REPO" status --short > "$OUT/git-status-after.txt"

diff -u \
  "$OUT/git-status-before.txt" \
  "$OUT/git-status-after.txt" \
  > "$OUT/git-status.diff" || true

echo
echo "Benchmark terminado."
echo "Resultados: $OUT"