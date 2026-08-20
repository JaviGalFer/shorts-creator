"""Safe projection of canonical pipeline metadata into a public JobResponse.

``metadata.json`` is canonical pipeline-owned state and is NEVER serialized
directly. This module extracts only the intentionally public fields into a
DTO allowlist and sanitizes warning/review reasons to stable codes.

No filesystem access, no raw metadata, no paths, no subprocess diagnostics.
"""

from __future__ import annotations

from shorts_creator.web.dto import JobResponse
from shorts_creator.web.repository import WebJob

# Transient running statuses produced by STAGE_STATUS_MAP (orchestrator).
_RUNNING_STATUSES = frozenset({
    "SCRIPT_GENERATING",
    "ASSETS_FETCHING",
    "AUDIO_GENERATING",
    "PREPARING",
    "RENDERING",
    "VALIDATING",
})

# Stable public reason codes we are willing to expose. Codes may carry a
# single colon with a short safe suffix (e.g. "MUSIC_ENABLED_NO_PATH: ...")
# but free-form fragments (exception reprs, error lists, confidences) are
# NOT exposed; unknown/unsafe entries collapse to a generic code.
_STABLE_REASON_PREFIXES = frozenset({
    "DURATION_FITTING_INVALID_INPUT",
    "DURATION_FITTING_EXHAUSTED",
    "DURATION_FITTING_REPAIR_FAILED",
    "DURATION_FITTING_AUDIO_REGENERATION_FAILED",
    "REQUESTED_DURATION_OUT_OF_RANGE",
    "AUDIO_DURATION_MISSING",
    "MUSIC_ENABLED_NO_PATH",
    "QUERY_NOT_SPECIFIC",
    "SEGMENT_QUERY_NOT_SPECIFIC",
    "MEDIA_PREFERENCE_MISSING",
    "VISUAL_PLAN_FAILURE",
    "GENERIC_REASON",
})

# Suspicious substrings that disqualify a raw reason from projection even if
# its prefix looks stable (they carry internal/diagnostic detail).
_UNSAFE_FRAGMENTS = (
    "confidence=",
    "{",
    "}",
    "errors=[",
    "Traceback",
    "/",
    "\\",
)


def _sanitize_reason(raw: str) -> str | None:
    """Return a stable public reason code or None if it must be suppressed."""
    if not isinstance(raw, str):
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    code_part = stripped.split(":", 1)[0].strip()
    if code_part not in _STABLE_REASON_PREFIXES:
        return None
    if any(fragment in stripped for fragment in _UNSAFE_FRAGMENTS):
        return code_part
    if ":" in stripped:
        return stripped[:120].rstrip()
    return code_part


def _sanitize_reasons(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        cleaned = _sanitize_reason(str(item))
        if cleaned is not None:
            out.append(cleaned)
    return out


def _derive_stages(metadata: dict) -> tuple[str | None, str | None]:
    """Return (current_stage, last_completed_stage) from orchestration."""
    orchestration = metadata.get("orchestration")
    if not isinstance(orchestration, dict):
        return None, None
    current = orchestration.get("currentStage")
    if not isinstance(current, str):
        current = None
    history = orchestration.get("statusHistory")
    last_completed: str | None = None
    if isinstance(history, list):
        completed_stages: list[str] = []
        for entry in history:
            if not isinstance(entry, dict):
                continue
            stage = entry.get("stage")
            status = entry.get("status")
            if isinstance(stage, str) and isinstance(status, str):
                if status not in _RUNNING_STATUSES and status not in ("UNKNOWN",):
                    completed_stages.append(stage)
        if completed_stages:
            last_completed = completed_stages[-1]
    return current, last_completed


def project_job(
    web_job: WebJob,
    metadata: dict,
    *,
    has_video: bool,
) -> JobResponse:
    """Project Web execution state + canonical metadata into the DTO.

    ``has_video`` is supplied by the caller from the authoritative
    filesystem existence check (repository.resolve_video_path), not inferred
    from status.
    """
    current_stage, last_completed = _derive_stages(metadata)
    pipeline_status = metadata.get("status")
    if not isinstance(pipeline_status, str) or not pipeline_status:
        pipeline_status = None

    return JobResponse(
        job_id=web_job.job_id,
        execution_state=web_job.execution_state,
        pipeline_status=pipeline_status,
        current_stage=current_stage,
        last_completed_stage=last_completed,
        created_at=web_job.created_at,
        started_at=web_job.started_at,
        finished_at=web_job.finished_at,
        has_video=has_video,
        warnings=_sanitize_reasons(metadata.get("warnings")),
        review_reasons=_sanitize_reasons(metadata.get("reviewReasons")),
    )