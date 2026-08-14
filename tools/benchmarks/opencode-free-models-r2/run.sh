#!/usr/bin/env bash
#
# OpenCode Free Models Benchmark R2 — runner harness.
#
# Runs 4 models x 2 tasks (R2-A read-only replay, R2-B hermetic build) using
# `opencode run` non-interactively. Metrics (wall-clock via /usr/bin/time,
# tool calls, tokens, PASS/FAIL, scope) are derived from the emitted
# `--format json` events plus fixture/test outcomes.
#
# NOT yet executed. This is the design for the future run. Run with:
#   bash tools/benchmarks/opencode-free-models-r2/run.sh
#
# Env overrides:
#   BASE_OUT       output dir (default ~/opencode-benchmarks/shorts-free-r2-<stamp>)
#   SKIP_R2A       set to 1 to skip R2-A
#   SKIP_R2B       set to 1 to skip R2-B

set -u

REPO="/home/javi/projects/shorts-creator"
BENCH="$REPO/tools/benchmarks/opencode-free-models-r2"
PY="${PYTHON:-python3}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BASE_OUT:-$HOME/opencode-benchmarks/shorts-free-r2-$STAMP}"

mkdir -p "$OUT"

# Build immutable fixture masters; each run clones its own copy.
bash "$BENCH/fixtures/build-r2a-fixture.sh" "$OUT/sandbox-r2a"
bash "$BENCH/fixtures/build-r2b-fixture.sh" "$OUT/sandbox-r2b"

# ---------------------------------------------------------------------------
# Preflight: confirm the benchmark agents are discoverable from each sandbox.
# Abort before any benchmark run if either agent is missing. Uses
# `opencode agent list` only — no model is invoked.
# ---------------------------------------------------------------------------
preflight_sandbox() {
  local sandbox="$1"
  local agent="$2"
  local scratch="$3"
  rm -rf "$scratch"
  cp -r "$sandbox" "$scratch"
  chmod -R a-w "$scratch"
  if ! out="$(cd "$scratch" && opencode agent list 2>&1)"; then
    echo "PREFLIGHT FAIL: opencode agent list errored for $(basename "$sandbox")" >&2
    exit 3
  fi
  if ! grep -q "^$agent (primary)" <<< "$out"; then
    echo "PREFLIGHT FAIL: agent '$agent' not found in $(basename "$sandbox")" >&2
    exit 3
  fi
  echo "PREFLIGHT OK: $agent found in $(basename "$sandbox")"
}

preflight_sandbox "$OUT/sandbox-r2a" "benchmark-readonly" "$OUT/preflight-r2a"
preflight_sandbox "$OUT/sandbox-r2b" "benchmark-builder" "$OUT/preflight-r2b"

# Explicit model order (reproducible; indexed parallel arrays, NO associative
# array and NO variable names containing '-').
MODEL_KEYS=(
  big-pickle
  deepseek-v4-flash-free
  nemotron-3.5-lightning-free
  laguna-s-2.1-free
)

MODEL_REFS=(
  opencode/big-pickle
  opencode/deepseek-v4-flash-free
  opencode/nemotron-3.5-lightning-free
  opencode/laguna-s-2.1-free
)

git -C "$REPO" rev-parse HEAD > "$OUT/commit.txt"
git -C "$REPO" status --short > "$OUT/git-status-before.txt"
(
  cd "$REPO" &&
  opencode stats --days 1 --models 20 --project ""
) > "$OUT/stats-before.txt" 2>&1

run_task() {
  local label="$1"
  local agent="$2"
  local sandbox="$3"
  local model="$4"
  local prompt="$5"
  local writable="$6"
  local scorer="$7"

  echo
  echo "=== $label | $model | variant=default ==="

  local outdir="$OUT/$label"
  mkdir -p "$outdir"

  local started finished rc
  started="$(date +%s)"

  # Each run gets its own throwaway copy of the fixture.
  rm -rf "$sandbox.$label"
  cp -r "$sandbox" "$sandbox.$label"
  if [[ "$writable" != "1" ]]; then
    # R2-A stays read-only. R2-B must remain writable for the agent edits.
    chmod -R a-w "$sandbox.$label"
  fi

  /usr/bin/time \
    -f "wall_seconds=%e\nuser_seconds=%U\nsystem_seconds=%S\nmax_rss_kb=%M" \
    -o "$outdir/time.txt" \
    opencode run \
      --dir "$sandbox.$label" \
      --model "$model" \
      --agent "$agent" \
      --variant default \
      --format json \
      --title "benchmark-r2-$label" \
      "$(sed "s|#WORKDIR#|$sandbox.$label|" "$prompt")" \
    > "$outdir/events.jsonl" \
    2> "$outdir/stderr.txt"

  rc=$?
  finished="$(date +%s)"
  printf '%s\n' "$rc" > "$outdir/exit-code.txt"
  printf '%s\n' "$((finished - started))" > "$outdir/elapsed-seconds.txt"

  echo "Exit code: $rc"
  echo "Elapsed: $((finished - started)) seconds"

  # Capture evidence check. OpenCode has produced streams where the final
  # text/step_finish is missing even though the session is persisted. Only in
  # that diagnostic case do we export the session (a CAPTURE artifact).
  # `opencode export` is NOT run on every run and its output is NOT consumed by
  # any scorer (no complex export parser here).
  local capture="$("$PY" "$BENCH/capture_evidence.py" "$outdir/events.jsonl")"
  local sid
  sid="$("$PY" "$BENCH/session_id.py" "$outdir/events.jsonl")"
  if [[ -z "$sid" ]]; then
    echo "none" > "$outdir/capture-fallback.txt"
    echo "WARN: no sessionID in stream"
  elif [[ "$capture" == "complete" ]]; then
    printf '%s\n' "$sid" > "$outdir/session-id.txt"
    echo "none" > "$outdir/capture-fallback.txt"
  else
    # Missing scoring evidence: export session as a diagnostic artifact only.
    printf '%s\n' "$sid" > "$outdir/session-id.txt"
    opencode export "$sid" > "$outdir/export.json" 2> "$outdir/export.stderr.txt"
    echo "export" > "$outdir/capture-fallback.txt"
    echo "CAPTURE_ERROR: evidence incomplete ($capture); exported session for diagnostics"
  fi

  # Score the run with its scorer. Incomplete capture is a CAPTURE_ERROR
  # (diagnostic), not a model FAIL. The scorer maps missing evidence to exit 2
  # (R2-A) / no-loop (R2-B); we record a CAPTURE_ERROR marker here so the
  # result is not conflated with a normal FAIL. Do NOT abort other models.
  local score_rc
  if [[ -n "$sid" && "$capture" != "complete" ]]; then
    echo "CAPTURE_ERROR" > "$outdir/score-exit-code.txt"
    echo "{\"capture\": \"$capture\", \"note\": \"incomplete evidence; export saved as diagnostic\"}" > "$outdir/score.json"
    echo "Score: CAPTURE_ERROR ($capture)"
  else
    if [[ "$scorer" == "score_r2a.py" ]]; then
      "$PY" "$BENCH/$scorer" "$outdir/events.jsonl" \
        > "$outdir/score.json" 2> "$outdir/score.stderr.txt"
    else
      "$PY" "$BENCH/$scorer" "$sandbox" "$sandbox.$label" "$outdir/events.jsonl" \
        > "$outdir/score.json" 2> "$outdir/score.stderr.txt"
    fi
    score_rc=$?
    printf '%s\n' "$score_rc" > "$outdir/score-exit-code.txt"
    echo "Score exit: $score_rc"
  fi

  sleep 30
}

for i in "${!MODEL_KEYS[@]}"; do
  model="${MODEL_KEYS[$i]}"
  mid="${MODEL_REFS[$i]}"

  if [[ "${SKIP_R2A:-0}" != "1" ]]; then
    run_task "r2a-$model" \
      benchmark-readonly \
      "$OUT/sandbox-r2a" \
      "$mid" \
      "$BENCH/prompts/r2a-prompt.txt" \
      "0" \
      "score_r2a.py"
  fi

  if [[ "${SKIP_R2B:-0}" != "1" ]]; then
    run_task "r2b-$model" \
      benchmark-builder \
      "$OUT/sandbox-r2b" \
      "$mid" \
      "$BENCH/prompts/r2b-prompt.txt" \
      "1" \
      "score_r2b.py"
  fi
done

(
  cd "$REPO" &&
  opencode stats --days 1 --models 20 --project ""
) > "$OUT/stats-after.txt" 2>&1

opencode session list -n 20 --format json > "$OUT/sessions-after.json" 2>&1

git -C "$REPO" status --short > "$OUT/git-status-after.txt"
diff -u "$OUT/git-status-before.txt" "$OUT/git-status-after.txt" > "$OUT/git-status.diff" || true

echo
echo "Benchmark R2 terminado (diseño). Resultados: $OUT"
