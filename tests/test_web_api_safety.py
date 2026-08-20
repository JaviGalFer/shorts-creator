"""HTTP security-surface tests: DTO allowlist, sanitized errors, stability.

The web API exposes domain resources, never the filesystem. These tests
assert that only known response fields are present, that error bodies are
structured and stable, and that no raw internal detail reaches the client.
"""

import pytest

from shorts_creator.web.exceptions import error_payload, to_http_error, to_http_internal_error


# ── error payloads ──────────────────────────────────────────────────────────


def test_known_error_maps_to_stable_code():
    from shorts_creator.web.exceptions import JobNotFoundError

    status, body = to_http_error(JobNotFoundError())
    assert status == 404
    assert body == {"error": {"code": "JOB_NOT_FOUND", "message": "Job not found."}}


def test_unknown_error_maps_to_internal_stable():
    status, body = to_http_internal_error(log_context="/x")
    assert status == 500
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "Traceback" not in str(body)
    assert isinstance(body["error"]["message"], str)


def test_error_payload_structure():
    from shorts_creator.web.exceptions import InvalidJobIdError

    payload = error_payload(InvalidJobIdError(message="bad id"))
    assert payload["error"]["code"] == "INVALID_JOB_ID"
    assert payload["error"]["message"] == "bad id"
    assert set(payload["error"].keys()) == {"code", "message"}


# ── DTO allowlist ───────────────────────────────────────────────────────────


def test_job_create_allows_known_fields_only():
    from shorts_creator.web.dto import JobCreate

    valid = JobCreate(
        topic="T",
        duration_preset="quick_30",
        tts_provider="edge_tts",
        voice="es-ES-RaquelNeural",
        visual_mode="AUTO",
        asset_providers=["wikimedia_commons"],
    )
    assert valid.topic == "T"
    assert valid.visual_mode.value == "AUTO"


def test_job_create_extra_field_rejected():
    from pydantic import ValidationError

    from shorts_creator.web.dto import JobCreate

    with pytest.raises(ValidationError):
        JobCreate(topic="T", unknown="x")


def test_visual_mode_enum_unknown_rejected():
    from pydantic import ValidationError

    from shorts_creator.web.dto import JobCreate

    with pytest.raises(ValidationError):
        JobCreate(topic="T", visual_mode="PSEUDO")


def test_tts_provider_enum_unknown_rejected():
    from pydantic import ValidationError

    from shorts_creator.web.dto import JobCreate

    with pytest.raises(ValidationError):
        JobCreate(topic="T", tts_provider="claude")


def test_job_response_shallow_field_set():
    from shorts_creator.web.dto import JobResponse

    allowed = {
        "job_id", "execution_state", "pipeline_status", "current_stage",
        "last_completed_stage", "created_at", "started_at", "finished_at",
        "has_video", "warnings", "review_reasons",
    }
    assert set(JobResponse.model_fields.keys()) == allowed

    # cross-check: internal metadata keys are never in the response schema
    for forbidden in ("childCommand", "failure", "outputVideoPath", "jobPath", "createRequest"):
        assert forbidden not in set(JobResponse.model_fields.keys())


# ── library / provider presence (no runtime secret leak) ────────────────────


def test_capabilities_do_not_leak_secret_values():
    from shorts_creator.web.capabilities import build_capabilities

    caps = build_capabilities()
    txt = str(caps.model_dump())
    for marker in ("ELEVENLABS_API_KEY", "sk-", "API_KEY="):
        assert marker not in txt


def test_health_shape_ok():
    from shorts_creator.web.dto import HealthResponse

    h = HealthResponse()
    assert h.status == "ok"