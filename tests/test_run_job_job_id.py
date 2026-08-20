"""Focused tests for explicit job-id propagation (Slice 1: reusable pipeline boundary).

All LLM calls are mocked — no live OpenAI requests. The canonical runner must
accept an explicit job_id (a safe filename-compatible identifier) so a future
web backend can run the pipeline with one identity:

    API jobId == directory jobId == metadata.jobId

Default behavior (job_id=None) must remain exactly the topic-derived path.
"""

import json as _json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_PROJECT = Path(__file__).resolve().parents[1]
_BIN = _PROJECT / "bin"
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

import generate_script as cli
from shorts_creator.pipeline import orchestrator
from shorts_creator.script import generator as gs
from shorts_creator.pipeline.orchestrator import (
    build_script_command,
    run_pipeline,
)

EXPLICIT_ID = "7ad706f5-34e3-4fe8-b7dd-b253b6b5cf9c"


# ── V2 script fixture (mirrors tests/test_generate_script_v2.py) ─────────────


def _v2_scene_vp(**overrides):
    vp = {
        "_schemaVersion": 2,
        "visualIntent": "explain",
        "subjects": ["azul media luz onda"],
        "searchQueries": [
            "blue visible light wavelength",
            "electromagnetic spectrum diagram",
        ],
        "assetPreferences": ["photograph", "diagram"],
        "visualSequence": [
            {
                "segmentIndex": 1,
                "assetPreference": "photograph",
                "durationFraction": 0.5,
                "transition": "cut",
            },
            {
                "segmentIndex": 2,
                "assetPreference": "diagram",
                "durationFraction": 0.5,
                "transition": "fade",
            },
        ],
    }
    vp.update(overrides)
    return vp


def _v2_scene(scene_number=1):
    return {
        "sceneNumber": scene_number,
        "voiceover": (
            f"Escena {scene_number}: la luz azul se dispersa mas y por eso vemos "
            "el cielo azul durante el dia en la atmosfera."
        ),
        "subtitle": f"Azul {scene_number}",
        "targetDurationSec": 7.5,
        "visualPlan": _v2_scene_vp(),
    }


def _v2_script(scenes=None):
    if scenes is None:
        scenes = [_v2_scene(i) for i in range(1, 5)]
    return {
        "title": "Por que el cielo es azul",
        "hook": "La luz azul se dispersa mas.",
        "summary": "Resumen de una linea",
        "totalTargetDurationSec": 30,
        "scenes": scenes,
    }


# ── Build-command helpers ────────────────────────────────────────────────────


def _make_args(job_id=None):
    return SimpleNamespace(
        topic="Test",
        duration=30,
        duration_profile=None,
        duration_preset=None,
        duration_tolerance=None,
        duration_target=None,
        duration_min=None,
        duration_max=None,
        strictness=None,
        model=None,
        audio_config=None,
        asset_providers=None,
        visual_mode=None,
        job_id=job_id,
    )


# ── 1. Default path keeps existing script command (no --job-id) ──────────────


def test_build_script_command_without_job_id_omits_flag():
    cmd = build_script_command(_make_args(job_id=None))
    assert cmd[1].endswith("generate_script.py")
    assert "--job-id" not in cmd
    assert cmd[cmd.index("--topic") + 1] == "Test"
    assert "--output" not in cmd


# ── 2. Explicit job_id propagates through the CLI adapter to generate_script ─


def test_build_script_command_with_explicit_job_id():
    cmd = build_script_command(_make_args(job_id=EXPLICIT_ID))
    assert cmd[cmd.index("--job-id") + 1] == EXPLICIT_ID


def test_cli_parser_accepts_job_id():
    args = cli.build_parser().parse_args(["--topic", "T", "--job-id", EXPLICIT_ID])
    assert args.job_id == EXPLICIT_ID


def test_cli_forwards_job_id_to_generate_script(monkeypatch):
    captured = {}

    def fake_generate_script(topic, **kwargs):
        captured["topic"] = topic
        captured["job_id"] = kwargs.get("job_id")
        return 0

    monkeypatch.setattr(gs, "generate_script", fake_generate_script)
    monkeypatch.setattr(
        sys, "argv", ["generate_script.py", "--topic", "T", "--job-id", EXPLICIT_ID]
    )
    rc = cli.main()
    assert rc == 0
    assert captured["topic"] == "T"
    assert captured["job_id"] == EXPLICIT_ID


# ── 3 & 4. Explicit ID determines directory + metadata.jobId (single identity) ─


def test_explicit_job_id_canonical_path_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(gs, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
    monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(_v2_script()))

    rc = gs.generate_script(topic="Test", job_id=EXPLICIT_ID, duration=30)
    assert rc == 0

    meta_path = tmp_path / "data" / "videos" / EXPLICIT_ID / "metadata.json"
    assert meta_path.exists(), "metadata must be at data/videos/<jobId>/metadata.json"
    meta = _json.loads(meta_path.read_text())
    assert meta["jobId"] == EXPLICIT_ID
    assert meta["status"] == "SCRIPT_DRAFT"


# ── 5. Topic-derived generate_job_id unchanged when no override ──────────────


def test_generate_job_id_topic_derived_shape():
    jid = gs.generate_job_id("Cómo se forma un arcoíris")
    assert jid.startswith("cmo-")
    assert re.fullmatch(r"[a-z0-9]+-\d{4}-\d{2}-\d{2}-\d{6}", jid)


def test_default_topic_job_id_still_used(tmp_path, monkeypatch):
    monkeypatch.setattr(gs, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
    monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(_v2_script()))

    # Deterministic: pin the topic-derived generator to a fixed safe ID so the
    # assertion does not depend on second-level clock crossing.
    calls = []
    fixed_jid = "prueba-derived-20260820-000000"

    def fake_generate_job_id(topic):
        calls.append(topic)
        return fixed_jid

    monkeypatch.setattr(gs, "generate_job_id", fake_generate_job_id)

    rc = gs.generate_script(topic="Prueba Israel", duration=30)
    assert rc == 0
    assert calls == ["Prueba Israel"], "default job_id=None must use topic-derived generator"
    meta_path = tmp_path / "data" / "videos" / fixed_jid / "metadata.json"
    assert meta_path.exists()
    meta = _json.loads(meta_path.read_text())
    assert meta["jobId"] == fixed_jid
    assert meta["status"] == "SCRIPT_DRAFT"


# ── 6. Unsafe explicit IDs are rejected ──────────────────────────────────────


@pytest.mark.parametrize(
    "bad",
    [
        "../escape",
        "..",
        "a/b",
        "a\\b",
        "",
        "a b",
        "a\x00b",
        "/etc/passwd",
        "..%2f..",
    ],
)
def test_validate_job_id_rejects_unsafe(bad):
    with pytest.raises(ValueError):
        gs.validate_job_id(bad)


@pytest.mark.parametrize("good", [EXPLICIT_ID, "abc-123", "job_1.2", "A1_b-c.d"])
def test_validate_job_id_accepts_safe(good):
    gs.validate_job_id(good)  # must not raise


def test_run_pipeline_rejects_unsafe_job_id():
    with pytest.raises(ValueError):
        run_pipeline(topic="Test", job_id="../../etc", dry_run_mode=True)


# ── 7. Pre-review hardening: fail-fast boundary + output conflict ────────────


def _fake_never_llm(calls):
    def _llm(*a, **kw):
        calls.append("call_llm")
        return _json.dumps(_v2_script())
    return _llm


def test_generate_script_invalid_explicit_job_id_fails_before_llm(monkeypatch):
    calls = []
    monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
    monkeypatch.setattr(gs, "call_llm", _fake_never_llm(calls))

    with pytest.raises(ValueError, match="INVALID_JOB_ID"):
        gs.generate_script(topic="Test", job_id="../escape", duration=30)

    assert calls == [], "call_llm must not run when an explicit job_id is invalid"


def test_generate_script_invalid_explicit_blank_job_id_fails_before_llm(monkeypatch):
    calls = []
    monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
    monkeypatch.setattr(gs, "call_llm", _fake_never_llm(calls))

    with pytest.raises(ValueError, match="INVALID_JOB_ID"):
        gs.generate_script(topic="Test", job_id="   ", duration=30)

    assert calls == []


def test_generate_script_rejects_job_id_with_output_before_llm(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(gs, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
    monkeypatch.setattr(gs, "call_llm", _fake_never_llm(calls))
    out = tmp_path / "custom" / "metadata.json"

    with pytest.raises(ValueError, match="JOB_ID_OUTPUT_CONFLICT"):
        gs.generate_script(topic="Test", job_id=EXPLICIT_ID, output=str(out), duration=30)

    assert calls == [], "call_llm must not run on job_id+output conflict"
    assert not out.exists(), "no filesystem output may be written on conflict"
    assert not (tmp_path / "data").exists(), "no canonical directory may be created on conflict"


def test_legacy_output_without_job_id_still_used(tmp_path, monkeypatch):
    monkeypatch.setattr(gs, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(gs, "load_env", lambda: {"LLM_API_KEY": "fake"})
    monkeypatch.setattr(gs, "call_llm", lambda *a, **kw: _json.dumps(_v2_script()))
    out = tmp_path / "custom" / "metadata.json"

    rc = gs.generate_script(topic="Prueba", output=str(out), duration=30)
    assert rc == 0
    assert out.exists(), "legacy --output must still write to the requested path"
    meta = _json.loads(out.read_text())
    jid = meta["jobId"]
    assert jid.startswith("prueba-"), "jobId stays topic-derived when no job_id is given"
    assert out.parent.name != jid, "custom --output directory must differ from canonical jobId dir"
    assert not (tmp_path / "data" / "videos" / jid / "metadata.json").exists()


def test_cli_parser_rejects_job_id_with_output():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(
            ["--topic", "T", "--job-id", EXPLICIT_ID, "--output", "x.json"]
        )


# ── 8. Pre-review hardening: explicit-ID canonical path authority ────────────


def fake_script_run(stdout: str):
    return lambda cmd, verbose, stage: subprocess.CompletedProcess(cmd, 0, stdout, "")


def test_run_pipeline_explicit_job_id_rejects_foreign_reported_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(orchestrator, "_project_root", lambda: tmp_path)
    canonical = tmp_path / "data" / "videos" / EXPLICIT_ID / "metadata.json"
    canonical.parent.mkdir(parents=True)
    canonical.write_text(_json.dumps({"jobId": EXPLICIT_ID, "status": "SCRIPT_DRAFT"}))
    foreign = tmp_path / "elsewhere" / "metadata.json"
    foreign.parent.mkdir(parents=True)
    foreign.write_text(_json.dumps({"jobId": EXPLICIT_ID, "status": "SCRIPT_DRAFT"}))
    reported = _json.dumps({"jobId": EXPLICIT_ID, "path": str(foreign), "status": "SCRIPT_DRAFT"})
    monkeypatch.setattr(orchestrator, "run_subprocess", fake_script_run(reported))

    rc = run_pipeline(topic="Test", job_id=EXPLICIT_ID, duration=30, stop_after="script")
    assert rc == 1, "a foreign reported path must fail the explicit-ID script stage"
    out = capsys.readouterr().out
    assert "SCRIPT_OUTPUT_CONTRACT_VIOLATION" in out
    # The authoritative canonical file must not be progressed past the stage.
    saved = _json.loads(canonical.read_text())
    assert "orchestration" not in saved


def test_run_pipeline_explicit_job_id_rejects_mismatched_child_job_id(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(orchestrator, "_project_root", lambda: tmp_path)
    canonical = tmp_path / "data" / "videos" / EXPLICIT_ID / "metadata.json"
    canonical.parent.mkdir(parents=True)
    canonical.write_text(_json.dumps({"jobId": EXPLICIT_ID, "status": "SCRIPT_DRAFT"}))
    reported = _json.dumps({"jobId": "other-id", "path": str(canonical), "status": "SCRIPT_DRAFT"})
    monkeypatch.setattr(orchestrator, "run_subprocess", fake_script_run(reported))

    rc = run_pipeline(topic="Test", job_id=EXPLICIT_ID, duration=30, stop_after="script")
    assert rc == 1, "a mismatched child-reported jobId must fail closed"
    out = capsys.readouterr().out
    assert "SCRIPT_OUTPUT_CONTRACT_VIOLATION" in out
    saved = _json.loads(canonical.read_text())
    assert "orchestration" not in saved


def test_run_pipeline_explicit_job_id_matching_canonical_accepts(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(orchestrator, "_project_root", lambda: tmp_path)
    canonical = tmp_path / "data" / "videos" / EXPLICIT_ID / "metadata.json"
    canonical.parent.mkdir(parents=True)
    canonical.write_text(_json.dumps({
        "jobId": EXPLICIT_ID, "status": "SCRIPT_DRAFT",
        "createdAt": "2026-08-20T00:00:00.000Z",
    }))
    reported = _json.dumps({"jobId": EXPLICIT_ID, "path": str(canonical), "status": "SCRIPT_DRAFT"})
    monkeypatch.setattr(orchestrator, "run_subprocess", fake_script_run(reported))

    rc = run_pipeline(topic="Test", job_id=EXPLICIT_ID, duration=30, stop_after="script")
    assert rc == 0, "matching explicit jobId + canonical path must be accepted"
    saved = _json.loads(canonical.read_text())
    assert saved["status"] == "SCRIPT_DRAFT"
    assert saved["orchestration"]["statusHistory"][-1]["status"] == "SCRIPT_DRAFT"


def test_run_pipeline_none_job_id_keeps_legacy_reported_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(orchestrator, "_project_root", lambda: tmp_path)
    reported = tmp_path / "data" / "videos" / "topic-id" / "metadata.json"
    reported.parent.mkdir(parents=True)
    reported.write_text(_json.dumps({
        "jobId": "topic-id", "status": "SCRIPT_DRAFT",
        "createdAt": "2026-08-20T00:00:00.000Z",
    }))
    stdout = _json.dumps({"jobId": "topic-id", "path": str(reported), "status": "SCRIPT_DRAFT"})
    monkeypatch.setattr(orchestrator, "run_subprocess", fake_script_run(stdout))

    rc = run_pipeline(topic="Test", duration=30, stop_after="script")
    assert rc == 0, "legacy no-job_id stdout discovery must remain accepted"
    saved = _json.loads(reported.read_text())
    assert saved["status"] == "SCRIPT_DRAFT"


# ── 9. Final identity hardening: loaded canonical metadata jobId is the contract ──


def test_run_pipeline_success_branch_rejects_metadata_job_id_mismatch(tmp_path, monkeypatch, capsys):
    """The canonical file itself is validated independently of a plausible stdout."""
    monkeypatch.setattr(orchestrator, "_project_root", lambda: tmp_path)
    canonical = tmp_path / "data" / "videos" / EXPLICIT_ID / "metadata.json"
    canonical.parent.mkdir(parents=True)
    original = {"jobId": "B", "status": "SCRIPT_DRAFT"}
    canonical.write_text(_json.dumps(original))
    # stdout looks fully correct: jobId=A + canonical path — proves the FILE resolves it.
    reported = _json.dumps({"jobId": EXPLICIT_ID, "path": str(canonical), "status": "SCRIPT_DRAFT"})
    monkeypatch.setattr(orchestrator, "run_subprocess", fake_script_run(reported))

    rc = run_pipeline(topic="Test", job_id=EXPLICIT_ID, duration=30, stop_after="script")
    assert rc == 1, "a canonical metadata declaring a different jobId must fail closed"
    out = capsys.readouterr().out
    assert "SCRIPT_OUTPUT_CONTRACT_VIOLATION" in out
    saved = _json.loads(canonical.read_text())
    assert saved == original, "mismatched canonical metadata must not be mutated"
    assert "orchestration" not in saved


def test_run_pipeline_failure_branch_rejects_metadata_job_id_mismatch(tmp_path, monkeypatch, capsys):
    """Identity mismatch is detected before set_failure: no FAILED/orchestration mutation."""
    monkeypatch.setattr(orchestrator, "_project_root", lambda: tmp_path)
    canonical = tmp_path / "data" / "videos" / EXPLICIT_ID / "metadata.json"
    canonical.parent.mkdir(parents=True)
    original = {"jobId": "B", "status": "SCRIPT_DRAFT"}
    canonical.write_text(_json.dumps(original))
    reported = _json.dumps({"jobId": EXPLICIT_ID, "path": str(canonical), "status": "SCRIPT_DRAFT"})
    monkeypatch.setattr(
        orchestrator, "run_subprocess",
        lambda cmd, verbose, stage: subprocess.CompletedProcess(cmd, 1, reported, ""),
    )

    rc = run_pipeline(topic="Test", job_id=EXPLICIT_ID, duration=30, stop_after="script")
    assert rc == 1
    out = capsys.readouterr().out
    assert "SCRIPT_OUTPUT_CONTRACT_VIOLATION" in out
    saved = _json.loads(canonical.read_text())
    assert saved == original, "mismatched canonical metadata must not be rewritten to FAILED"
    assert "failure" not in saved
    assert "orchestration" not in saved


def test_run_pipeline_explicit_job_id_tolerates_malformed_stdout_when_identity_valid(tmp_path, monkeypatch, capsys):
    """Malformed/missing stdout stays acceptable when the canonical identity is valid."""
    monkeypatch.setattr(orchestrator, "_project_root", lambda: tmp_path)
    canonical = tmp_path / "data" / "videos" / EXPLICIT_ID / "metadata.json"
    canonical.parent.mkdir(parents=True)
    canonical.write_text(_json.dumps({
        "jobId": EXPLICIT_ID, "status": "SCRIPT_DRAFT",
        "createdAt": "2026-08-20T00:00:00.000Z",
    }))
    monkeypatch.setattr(orchestrator, "run_subprocess", fake_script_run("not-json output\n"))

    rc = run_pipeline(topic="Test", job_id=EXPLICIT_ID, duration=30, stop_after="script")
    assert rc == 0, "explicit-ID invocation must not make stdout mandatory"
    saved = _json.loads(canonical.read_text())
    assert saved["status"] == "SCRIPT_DRAFT"
    assert saved["orchestration"]["statusHistory"][-1]["status"] == "SCRIPT_DRAFT"
