"""JobProjection tests: metadata.json -> public allowlist DTO.

Verifies REVIEW_REQUIRED / ASSETS_PARTIAL / VALIDATED projection, stage
derivation, warning/review-reason sanitization, and that internal fields
(childCommand, failure, paths) never appear in the public response.
"""

import json
import uuid

from shorts_creator.web.dto import JobResponse
from shorts_creator.web.projection import project_job
from shorts_creator.web.repository import WebJob


def _uid():
    return str(uuid.uuid4())


def _web_job(state="FINISHED", **overrides):
    base = dict(
        job_id=_uid(),
        execution_state=state,
        created_at="2026-08-20T00:00:00.000Z",
        started_at="2026-08-20T00:00:01.000Z",
        finished_at="2026-08-20T00:00:02.000Z",
    )
    base.update(overrides)
    return WebJob(**base)


def _with_orchestration(metadata: dict, stages):
    history = [{"stage": s, "status": st, "startedAt": "t", "finishedAt": "t"}
               for s, st in stages]
    metadata.setdefault("orchestration", {})
    metadata["orchestration"]["currentStage"] = stages[-1][0]
    metadata["orchestration"]["statusHistory"] = history
    return metadata


def test_projects_review_required():
    web = _web_job()
    metadata = {
        "status": "REVIEW_REQUIRED",
        "reviewReasons": ["DURATION_FITTING_EXHAUSTED"],
    }
    metadata = _with_orchestration(metadata, [("script", "SCRIPT_DRAFT"), ("assets", "REVIEW_REQUIRED")])
    out = project_job(web, metadata, has_video=False)
    assert out.execution_state == "FINISHED"
    assert out.pipeline_status == "REVIEW_REQUIRED"
    assert out.last_completed_stage == "assets"
    assert out.review_reasons == ["DURATION_FITTING_EXHAUSTED"]


def test_projects_assets_partial():
    web = _web_job()
    metadata = {"status": "ASSETS_PARTIAL"}
    out = project_job(web, metadata, has_video=False)
    assert out.pipeline_status == "ASSETS_PARTIAL"
    assert out.has_video is False


def test_projects_validated_with_video():
    web = _web_job()
    metadata = {
        "status": "VALIDATED",
        "orchestration": {
            "currentStage": "validate",
            "statusHistory": [
                {"stage": "render", "status": "RENDERED"},
                {"stage": "validate", "status": "VALIDATED"},
            ],
        },
    }
    out = project_job(web, metadata, has_video=True)
    assert out.pipeline_status == "VALIDATED"
    assert out.has_video is True
    assert out.last_completed_stage == "validate"


def test_warning_and_reason_sanitization_drops_internal_fragments():
    web = _web_job()
    metadata = {
        "status": "REVIEW_REQUIRED",
        "warnings": ["QUERY_NOT_SPECIFIC: query X", "free-form internal detail"],
        "reviewReasons": [
            "MUSIC_ENABLED_NO_PATH: source missing",
            "DURATION_FITTING_REPAIR_FAILED: ['some', 'errors']",
            "canonicalMatching: confidence=0.5",
        ],
    }
    out = project_job(web, metadata, has_video=False)
    # Known stable prefixes kept; internal fragments collapsed/suppressed.
    warnings_joined = " ".join(out.warnings)
    reasons_joined = " ".join(out.review_reasons)
    assert "QUERY_NOT_SPECIFIC" in warnings_joined
    assert "DURATION_FITTING_REPAIR_FAILED" in reasons_joined
    assert "confidence" not in reasons_joined
    assert "free-form internal detail" not in warnings_joined


def test_child_command_and_failure_never_projected():
    web = _web_job(state="FAILED")
    metadata = {
        "status": "FAILED",
        "failure": {
            "failedStage": "render",
            "error": "some stderr",
            "childCommand": "python3 bin/render_job.py /secret/path/metadata.json",
            "exitCode": 1,
        },
    }
    out = project_job(web, metadata, has_video=False)
    dump = out.model_dump().values()
    joined = json.dumps(out.model_dump())
    assert out.execution_state == "FAILED"
    assert "/secret/path" not in joined
    assert "render_job.py" not in joined
    assert "childCommand" not in out.model_dump()
    assert set(out.model_dump().keys()) == {
        "job_id", "execution_state", "pipeline_status", "current_stage",
        "last_completed_stage", "created_at", "started_at", "finished_at",
        "has_video", "warnings", "review_reasons",
    }


def test_stages_with_running_status_excluded_from_last_completed():
    web = _web_job()
    metadata = {"status": "ASSETS_FETCHING"}
    metadata = _with_orchestration(
        metadata,
        [("script", "SCRIPT_DRAFT"), ("assets", "ASSETS_FETCHING")],
    )
    out = project_job(web, metadata, has_video=False)
    # ASSETS_FETCHING is running (transient) -> excludes from last completed.
    assert out.last_completed_stage == "script"
    assert out.current_stage == "assets"