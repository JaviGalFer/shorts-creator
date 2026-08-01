#!/usr/bin/env python3
"""Unified job runner for shorts-creator pipeline.

Orchestrates pipeline stages in dependency order, verifies each stage's
output contract (status + artifacts) before proceeding.

Usage:
  python3 bin/run_job.py --topic "Cómo se forma un arcoíris" --duration 42
  python3 bin/run_job.py --topic "Prueba" --duration 35 --stop-after script
  python3 bin/run_job.py --topic "Prueba" --duration 42 --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from duration_profiles import add_duration_profile_args, resolve_requested_duration

ORCHESTRATION_VERSION = "1"

STAGES = ["script", "assets", "audio", "prepare", "render", "validate"]

STAGE_SCRIPTS = {
    "audio": "generate_audio.py",
    "prepare": "prepare_job.py",
    "render": "render_job.py",
    "validate": "validate_job.py",
}

STAGE_STATUS_MAP = {
    "script":   {"running": "SCRIPT_GENERATING", "success": "SCRIPT_DRAFT"},
    "assets":   {"running": "ASSETS_FETCHING",   "success": "ASSETS_READY"},
    "audio":    {"running": "AUDIO_GENERATING",  "success": "AUDIO_READY"},
    "prepare":  {"running": "PREPARING",         "success": "SUBTITLES_READY"},
    "render":   {"running": "RENDERING",         "success": "RENDERED"},
    "validate": {"running": "VALIDATING",        "success": "VALIDATED"},
}

RENDER_SUCCESS_STATUSES = {"RENDERED", "RENDERED_WITH_WARNINGS", "RENDERED_WITH_ASSET_WARNINGS"}
REVIEW_BLOCKING_STAGES = {"assets", "audio", "prepare", "render", "validate"}
V2_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})

V1_POSITIVE_FIELDS: frozenset[str] = frozenset({"editorialRole", "strategy"})


def _classify_visual_schema(metadata: dict) -> str:
    if not isinstance(metadata, dict) or not metadata:
        return "SCHEMA_NOT_AVAILABLE_YET"
    script = metadata.get("script")
    if not isinstance(script, dict):
        return "SCHEMA_NOT_AVAILABLE_YET"
    scenes = script.get("scenes")
    if not isinstance(scenes, list):
        return "INVALID_SCHEMA"
    if not scenes:
        return "INVALID_SCHEMA"

    req = metadata.get("request")
    if isinstance(req, dict):
        visuals = req.get("visuals")
        if isinstance(visuals, dict) and "schemaVersion" in visuals:
            sv = visuals["schemaVersion"]
            if not isinstance(sv, int) or isinstance(sv, bool) or sv != 2:
                return "INVALID_SCHEMA"

    has_v2 = False
    has_v1 = False
    has_invalid = False

    for scene in scenes:
        if not isinstance(scene, dict):
            has_invalid = True
            continue
        vp = scene.get("visualPlan")
        if vp is None:
            has_invalid = True
            continue
        if not isinstance(vp, dict):
            has_invalid = True
            continue
        sv = vp.get("_schemaVersion")
        if isinstance(sv, int) and not isinstance(sv, bool):
            if sv == 2:
                has_v2 = True
            else:
                has_invalid = True
        elif sv is None:
            if V1_POSITIVE_FIELDS.intersection(vp.keys()):
                has_v1 = True
            else:
                has_invalid = True
        else:
            has_invalid = True

    if has_invalid:
        return "INVALID_SCHEMA"
    if has_v2 and has_v1:
        return "MIXED_SCHEMA"
    if has_v2:
        return "SUPPORTED_V2"
    if has_v1:
        return "UNSUPPORTED_LEGACY_V1"
    return "INVALID_SCHEMA"


def _schema_error_for_category(category: str) -> str | None:
    mapping = {
        "UNSUPPORTED_LEGACY_V1": "UNSUPPORTED_LEGACY_SCHEMA",
        "MIXED_SCHEMA": "MIXED_VISUAL_PLAN_SCHEMA_VERSIONS",
        "INVALID_SCHEMA": "INVALID_VISUAL_SCHEMA",
    }
    return mapping.get(category)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _script_path(name: str) -> str:
    return str(_project_root() / "bin" / name)


def build_script_command(args) -> list[str]:
    cmd = [sys.executable, _script_path("generate_script.py")]
    cmd.extend(["--topic", args.topic])
    if args.duration is not None:
        cmd.extend(["--duration", str(args.duration)])
    if args.duration_profile is not None:
        cmd.extend(["--duration-profile", args.duration_profile])
    if args.duration_target is not None:
        cmd.extend(["--duration-target", str(args.duration_target)])
    if args.duration_min is not None:
        cmd.extend(["--duration-min", str(args.duration_min)])
    if args.duration_max is not None:
        cmd.extend(["--duration-max", str(args.duration_max)])
    if args.strictness is not None:
        cmd.extend(["--strictness", args.strictness])
    if args.model is not None:
        cmd.extend(["--model", args.model])
    return cmd


def build_stage_command(stage: str, metadata_path: str, metadata: dict | None = None) -> list[str]:
    if stage == "assets":
        return [sys.executable, _script_path("fetch_images_v2.py"), metadata_path]
    script = STAGE_SCRIPTS.get(stage)
    if not script:
        raise ValueError(f"Unknown stage: {stage}")
    return [sys.executable, _script_path(script), metadata_path]


def run_subprocess(cmd: list[str], verbose: bool, stage: str) -> subprocess.CompletedProcess:
    if verbose:
        print(f"[{stage}] Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=_project_root(),
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            cmd, returncode=-1,
            stdout="", stderr="[TIMEOUT] Stage exceeded 600s limit"
        )
    return result


def parse_script_output(stdout: str) -> dict | None:
    for line in stdout.strip().split("\n"):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
                if "jobId" in data and "path" in data:
                    return data
            except json.JSONDecodeError:
                continue
    return None


def load_metadata(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def save_metadata(path: str, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def append_orchestration(
    data: dict,
    stage: str,
    status: str,
    started_at: str,
    finished_at: str,
    error: str | None = None,
) -> dict:
    orchestration = data.setdefault("orchestration", {})
    orchestration.setdefault("runnerVersion", ORCHESTRATION_VERSION)
    orchestration["currentStage"] = stage
    history = orchestration.setdefault("statusHistory", [])
    entry = {
        "stage": stage,
        "status": status,
        "startedAt": started_at,
        "finishedAt": finished_at,
    }
    if error:
        entry["error"] = error
    history.append(entry)
    return data


def set_failure(
    data: dict,
    stage: str,
    error_summary: str,
    command: list[str],
    exit_code: int | None = None,
) -> dict:
    data["status"] = "FAILED"
    data["failure"] = {
        "failedStage": stage,
        "error": error_summary[:1000],
        "childCommand": " ".join(command),
        "exitCode": exit_code,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    return data


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def resolve_duration_for_dry_run(args) -> dict | None:
    try:
        return resolve_requested_duration(
            requested_sec=args.duration,
            requested_profile=args.duration_profile,
            explicit_target=args.duration_target,
            explicit_min=args.duration_min,
            explicit_max=args.duration_max,
            explicit_strictness=args.strictness,
        )
    except ValueError:
        return None


def _verify_stage_contract(
    stage: str,
    data: dict,
    metadata_path: str,
    result: subprocess.CompletedProcess,
) -> tuple[bool, str, str | None]:
    """Verify post-stage output contract.

    Returns (ok, actual_status, error_message).

    When ok=True:       stage passed its contract.
    When ok=False and error is None:  known blocking status — stop gracefully.
    When ok=False and error is set:   contract violation — set FAILED.
    """
    video_dir = Path(metadata_path).parent
    actual_status = data.get("status", "UNKNOWN")

    if stage == "assets":
        assets_dir = video_dir / "assets"
        images = []
        if assets_dir.exists():
            images = [f for f in assets_dir.iterdir()
                      if f.is_file() and f.suffix.lower() in V2_IMAGE_EXTENSIONS]

        if actual_status == "ASSETS_READY":
            if images:
                return True, "ASSETS_READY", None
            return False, actual_status, (
                "STAGE_OUTPUT_CONTRACT_FAILED: assets exited 0 with status ASSETS_READY "
                f"but no images found in {assets_dir}"
            )
        if actual_status == "ASSET_UNRESOLVED":
            return False, "ASSET_UNRESOLVED", None
        if actual_status == "ASSETS_PARTIAL":
            return False, "ASSETS_PARTIAL", None
        if actual_status == "REVIEW_REQUIRED":
            return False, "REVIEW_REQUIRED", None
        return False, actual_status, (
            "STAGE_OUTPUT_CONTRACT_FAILED: assets exited 0 but metadata status is "
            f"{actual_status} (expected ASSETS_READY, ASSET_UNRESOLVED, ASSETS_PARTIAL, or REVIEW_REQUIRED)"
        )

    if stage == "audio":
        if actual_status == "AUDIO_READY":
            scenes_dir = video_dir / "scenes"
            narration = scenes_dir / "narration.mp3"
            if narration.exists():
                return True, "AUDIO_READY", None
            scene_files = sorted((scenes_dir.glob("scene-*.mp3"))) if scenes_dir.exists() else []
            if scene_files:
                return True, "AUDIO_READY", None
            return False, actual_status, (
                "STAGE_OUTPUT_CONTRACT_FAILED: audio exited 0 with status AUDIO_READY "
                f"but no narration audio found in {scenes_dir}"
            )
        if actual_status == "REVIEW_REQUIRED":
            return False, "REVIEW_REQUIRED", None
        return False, actual_status, (
            "STAGE_OUTPUT_CONTRACT_FAILED: audio exited 0 but metadata status is "
            f"{actual_status} (expected AUDIO_READY or REVIEW_REQUIRED)"
        )

    if stage == "prepare":
        sub_info = data.get("subtitles", {})
        sub_path_str = sub_info.get("path", "")
        sub_path = Path(sub_path_str) if sub_path_str else None
        render_info = data.get("render", {})
        has_timeline = "renderTimeline" in data
        render_path_str = render_info.get("path", "")

        errors = []
        if actual_status != "SUBTITLES_READY":
            errors.append(f"metadata status is {actual_status}, expected SUBTITLES_READY")
        if not sub_path or not sub_path.exists():
            errors.append(f"subtitle file missing: {sub_path}")
        if not render_path_str:
            errors.append("render.path not set in metadata")
        if not has_timeline:
            errors.append("renderTimeline missing from metadata")

        if errors:
            return False, actual_status, (
                "STAGE_OUTPUT_CONTRACT_FAILED: prepare exited 0 but contract not satisfied. "
                + "; ".join(errors)
            )
        return True, "SUBTITLES_READY", None

    if stage == "render":
        if actual_status in RENDER_SUCCESS_STATUSES:
            video_path = video_dir / "video.mp4"
            if video_path.exists():
                return True, actual_status, None
            return False, actual_status, (
                "STAGE_OUTPUT_CONTRACT_FAILED: render reports "
                f"{actual_status} but video.mp4 not found at {video_path}"
            )
        if actual_status in ("RENDER_FAILED", "ASSET_FAILED", "REVIEW_REQUIRED", "RENDER_SKIPPED"):
            return False, actual_status, None
        return False, actual_status, (
            "STAGE_OUTPUT_CONTRACT_FAILED: render exited 0 but metadata status is "
            f"{actual_status} (expected RENDERED, RENDERED_WITH_WARNINGS, or "
            "RENDERED_WITH_ASSET_WARNINGS)"
        )

    if stage == "validate":
        video_path = video_dir / "video.mp4"
        if not video_path.exists():
            return False, actual_status, (
                "STAGE_OUTPUT_CONTRACT_FAILED: validate requires video.mp4 but it does "
                f"not exist at {video_path}"
            )
        if result.returncode != 0:
            return False, "VALIDATION_FAILED", None
        # Exit 0: all checks passed
        return True, "VALIDATED", None

    return False, "UNKNOWN", f"Unknown stage: {stage}"


def dry_run(args) -> int:
    print("=== RUNNER DRY-RUN ===")
    print(f"Topic: {args.topic}")
    resolved = resolve_duration_for_dry_run(args)
    if resolved:
        print(f"Duration: {resolved['targetSec']}s "
              f"(profile={resolved['profile_name']}, "
              f"range={resolved['minSec']}-{resolved['maxSec']}s, "
              f"strictness={resolved['strictness']})")
    else:
        print("Duration: ERROR (invalid combination)")
    print(f"Stop after: {args.stop_after}")
    print()

    stop_at = args.stop_after
    plan = STAGES[:STAGES.index(stop_at) + 1]
    print("=== EXECUTION PLAN ===")
    for stage in plan:
        s = STAGE_STATUS_MAP[stage]
        print(f"\n[{stage}] {s['running']} -> {s['success']}")
        if stage == "script":
            cmd = build_script_command(args)
        else:
            cmd = build_stage_command(stage, "data/videos/{jobId}/metadata.json")
        print(f"  Command: {' '.join(cmd)}")
    print("\n=== END DRY-RUN ===")
    return 0


def _final_summary(data: dict | None, metadata_path: str | None, last_stage: str) -> None:
    if data is None:
        print(json.dumps({"status": "FAILED", "lastCompletedStage": last_stage}))
        return

    job_path = str(Path(metadata_path).parent) if metadata_path else None
    video_path = None
    validation_status = None
    s = data.get("status", "UNKNOWN")
    if s in ("RENDERED", "RENDERED_WITH_WARNINGS", "RENDERED_WITH_ASSET_WARNINGS", "VALIDATED", "APPROVED"):
        if metadata_path:
            vp = Path(metadata_path).parent / "video.mp4"
            if vp.exists():
                video_path = str(vp)
        validation_sec = data.get("validation", {})
        if s in ("VALIDATED", "APPROVED"):
            validation_status = validation_sec.get("status") or "PASS"

    print(json.dumps({
        "jobId": data.get("jobId", "unknown"),
        "jobPath": job_path,
        "status": s,
        "lastCompletedStage": last_stage,
        "outputVideoPath": video_path,
        "validationStatus": validation_status,
    }))


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified job runner for shorts-creator pipeline")
    parser.add_argument("--topic", required=True, help="Topic or instruction for the video")
    parser.add_argument("--model", help="LLM model override")
    parser.add_argument("--dry-run", action="store_true", help="Print execution plan without running")
    parser.add_argument("--stop-after", choices=STAGES, default="validate",
                        help="Stop after completing this stage (default: validate = full pipeline)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print child command output during execution")
    add_duration_profile_args(parser)
    args = parser.parse_args()

    if args.dry_run:
        return dry_run(args)

    stop_at = args.stop_after
    stage_plan = STAGES[:STAGES.index(stop_at) + 1]
    metadata_path: str | None = None
    data: dict | None = None

    for stage in stage_plan:
        if stage == "script":
            cmd = build_script_command(args)
            if args.verbose:
                print(f"[script] Running: python3 bin/generate_script.py ...")

            result = run_subprocess(cmd, args.verbose, "script")

            if result.returncode != 0:
                stderr = (result.stderr or "").strip()[:500]
                err_msg = stderr or f"exit code {result.returncode}"
                print(f"ERROR [script]: {err_msg}")
                parsed = parse_script_output(result.stdout or "")
                if parsed and "path" in parsed:
                    mp = parsed["path"]
                    if os.path.exists(mp):
                        metadata_path = mp
                        data = load_metadata(mp)
                        started = data.get("createdAt", _utcnow())
                        set_failure(data, "script", err_msg, cmd, result.returncode)
                        append_orchestration(data, "script", "FAILED", started, _utcnow(), err_msg)
                        save_metadata(mp, data)
                _final_summary(data, metadata_path, "script")
                return 1

            parsed = parse_script_output(result.stdout or "")
            if not parsed or "path" not in parsed:
                print("ERROR [script]: could not find job path in output")
                print(f"Stdout: {(result.stdout or '')[:500]}")
                _final_summary(None, None, "script")
                return 1

            metadata_path = parsed["path"]
            if not os.path.exists(metadata_path):
                print(f"ERROR [script]: metadata file not found at {metadata_path}")
                _final_summary(None, None, "script")
                return 1

            data = load_metadata(metadata_path)
            started = data.get("createdAt", _utcnow())
            finished = _utcnow()
            actual_status = data.get("status", "SCRIPT_DRAFT")

            if actual_status == "REVIEW_REQUIRED":
                print(f"REVIEW_REQUIRED: job {data.get('jobId', '?')} needs human review")
                append_orchestration(data, "script", "REVIEW_REQUIRED", started, finished)
                data["status"] = "REVIEW_REQUIRED"
                save_metadata(metadata_path, data)
                _final_summary(data, metadata_path, "script")
                return 0

            append_orchestration(data, "script", "SCRIPT_DRAFT", started, finished)
            data["status"] = "SCRIPT_DRAFT"
            save_metadata(metadata_path, data)
            print(f"[script] Job {data.get('jobId', '?')} ready at {metadata_path}")

        else:
            if not metadata_path or not os.path.exists(metadata_path):
                print(f"ERROR [{stage}]: no metadata available")
                _final_summary(None, None, stage)
                return 1

            data = load_metadata(metadata_path)

            schema_category = _classify_visual_schema(data)
            if schema_category != "SUPPORTED_V2":
                schema_error = _schema_error_for_category(schema_category)
                if schema_error is None:
                    schema_error = "INVALID_VISUAL_SCHEMA"
                print(f"ERROR [{stage}]: {schema_error}")
                started = _utcnow()
                set_failure(data, stage, schema_error, [], exit_code=0)
                append_orchestration(data, stage, "FAILED", started, _utcnow(), schema_error)
                save_metadata(metadata_path, data)
                _final_summary(data, metadata_path, stage)
                return 1

            if data.get("status") == "REVIEW_REQUIRED" and stage in REVIEW_BLOCKING_STAGES:
                print(f"REVIEW_REQUIRED: job blocked at stage '{stage}'. Needs human review.")
                _final_summary(data, metadata_path, stage)
                return 0

            cmd = build_stage_command(stage, metadata_path, metadata=data)
            started = _utcnow()
            orchestration = data.setdefault("orchestration", {})
            orchestration["currentStage"] = stage

            running_status = STAGE_STATUS_MAP[stage]["running"]
            data["status"] = running_status
            append_orchestration(data, stage, running_status, started, started)
            save_metadata(metadata_path, data)

            result = run_subprocess(cmd, args.verbose, stage)
            finished = _utcnow()

            data = load_metadata(metadata_path)
            actual_status = data.get("status", running_status)

            # --- Handle render special case: exit code 1 but video rendered ---
            # render_job.py returns 1 for RENDERED_WITH_WARNINGS and
            # RENDERED_WITH_ASSET_WARNINGS even though the video was produced.
            if stage == "render" and result.returncode != 0:
                if actual_status in RENDER_SUCCESS_STATUSES:
                    video_path = Path(metadata_path).parent / "video.mp4"
                    if video_path.exists():
                        print(f"[render] Note: render_job.py exited {result.returncode} "
                              f"but status is {actual_status} and video.mp4 exists. "
                              "Treating as render success.")
                        # Accept the rendering as successful
                    else:
                        stderr = (result.stderr or "").strip()[:500]
                        err_msg = stderr or f"exit code {result.returncode}"
                        print(f"ERROR [render]: exit code {result.returncode}")
                        if stderr:
                            print(f"  {stderr}")
                        set_failure(data, "render", err_msg, cmd, result.returncode)
                        append_orchestration(data, "render", "FAILED", started, finished, err_msg)
                        save_metadata(metadata_path, data)
                        _final_summary(data, metadata_path, "render")
                        return 1
                else:
                    stderr = (result.stderr or "").strip()[:500]
                    err_msg = stderr or f"exit code {result.returncode}"
                    print(f"ERROR [render]: exit code {result.returncode}")
                    if stderr:
                        print(f"  {stderr}")
                    set_failure(data, "render", err_msg, cmd, result.returncode)
                    append_orchestration(data, "render", "FAILED", started, finished, err_msg)
                    save_metadata(metadata_path, data)
                    _final_summary(data, metadata_path, "render")
                    return 1

            # Regular non-zero exit (for non-render stages, or render without recovery)
            elif result.returncode != 0:
                stderr = (result.stderr or "").strip()[:500]
                err_msg = stderr or f"exit code {result.returncode}"
                print(f"ERROR [{stage}]: exit code {result.returncode}")
                if stderr:
                    print(f"  {stderr}")
                set_failure(data, stage, err_msg, cmd, result.returncode)
                append_orchestration(data, stage, "FAILED", started, finished, err_msg)
                save_metadata(metadata_path, data)
                _final_summary(data, metadata_path, stage)
                return 1

            # --- Verify output contract ---
            ok, resolved_status, contract_error = _verify_stage_contract(
                stage, data, metadata_path, result
            )

            if not ok and contract_error:
                # Contract violation: child exited 0 but output doesn't satisfy contract
                print(f"ERROR [{stage}]: {contract_error}")
                set_failure(data, stage, contract_error, cmd, exit_code=0)
                append_orchestration(data, stage, "FAILED", started, finished, contract_error)
                save_metadata(metadata_path, data)
                _final_summary(data, metadata_path, stage)
                return 1

            if not ok and contract_error is None:
                # Known blocking status (REVIEW_REQUIRED, ASSET_UNRESOLVED, etc.)
                append_orchestration(data, stage, resolved_status, started, finished)
                save_metadata(metadata_path, data)
                print(f"[{stage}] Blocked: {resolved_status}")
                _final_summary(data, metadata_path, stage)
                return 0

            # Success
            append_orchestration(data, stage, resolved_status, started, finished)
            save_metadata(metadata_path, data)
            print(f"[{stage}] Completed: {resolved_status}")

        if stage == stop_at:
            break

    if metadata_path and os.path.exists(metadata_path):
        data = load_metadata(metadata_path)
    _final_summary(data, metadata_path, stage_plan[-1] if stage_plan else "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
