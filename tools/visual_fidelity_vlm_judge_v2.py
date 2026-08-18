#!/usr/bin/env python3
"""Evaluation-only multimodal judge benchmark for visual-fidelity-vlm-judge-v2.

COMPARED TO ``tools/visual_fidelity_api_benchmark.py`` (Slice 3A) this is a
LESS conservative judge contract: three-way verdict (ACCEPT / REJECT /
UNCERTAIN) with operational fail-open (UNCERTAIN becomes ACCEPT), and
REJECT only on material mismatches. It is deliberately outside the production
runtime: it uses the official OpenAI Python SDK lazily, sends one independent
Responses API request per asset, and requires an explicit preflight before
execution.

Behavior contract:
  - Reads a labels JSON (canonical 38 or development 20), builds one request
    per asset with the judge V2 contract, and NEVER sends humanLabel, other
    models' scores/verdicts, or any expected verdict.
  - The optional ``assetPreference`` semantic input is read from the persisted
    segment contract in ``data/videos/<jobId>/metadata.json`` (joined by
    jobId/sceneNumber/segmentIndex) and sent ONLY when it is part of that
    contract.
  - GIF images: frame 0, without mutating the file (matches the human
    benchmark convention).
  - Preflight counts input tokens per request (non-secret fingerprint),
    projects cost with reference pricing, and ABORTS without executing if the
    projected max total exceeds the hard cap.
  - Structured Output is strict JSON schema; per-asset model errors are
    recorded independently and never abort the phase.
  - No API key and no base64 image payloads are ever persisted.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import mimetypes
import os
import statistics
import sys
import time
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = str(_PROJECT_ROOT / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from visual_fidelity_benchmark import (  # noqa: E402
    ACCEPT,
    REJECT,
    evaluate_verdicts,
    load_labels,
    validate_labels,
)

MODEL = "gpt-5.6-luna"
DETAIL = "high"
REASONING_EFFORT = "none"
MAX_OUTPUT_TOKENS = 128
MAX_TOTAL_COST_USD = 0.10
INPUT_PRICE_USD_PER_MILLION = 0.20
CACHED_INPUT_PRICE_USD_PER_MILLION = 0.02
OUTPUT_PRICE_USD_PER_MILLION = 1.20
PRICING_REFERENCE_DATE = "2026-08-18"
PROMPT_SCHEMA_VERSION = "vlm-judge-v2"

UNCERTAIN = "UNCERTAIN"

# Reason codes; verdicts allowed per reason code (see the mapping table).
ACCEPT_CODES = (
    "MATCH",
)
REJECT_CODES = (
    "WRONG_ENTITY",
    "WRONG_VARIANT_OR_ERA",
    "WRONG_ACTION_OR_SCENE",
    "WRONG_CONTENT_TYPE",
    "MISSING_ESSENTIAL_RELATION",
    "FACTUAL_CONTRADICTION",
    "IRRELEVANT",
)
UNCERTAIN_CODES = (
    "INSUFFICIENT_VISUAL_EVIDENCE",
)
REASON_CODE_VERDICTS: dict[str, tuple[str, ...]] = {
    "MATCH": (ACCEPT,),
    "WRONG_ENTITY": (REJECT,),
    "WRONG_VARIANT_OR_ERA": (REJECT,),
    "WRONG_ACTION_OR_SCENE": (REJECT,),
    "WRONG_CONTENT_TYPE": (REJECT,),
    "MISSING_ESSENTIAL_RELATION": (REJECT,),
    "FACTUAL_CONTRADICTION": (REJECT,),
    "IRRELEVANT": (REJECT,),
    "INSUFFICIENT_VISUAL_EVIDENCE": (ACCEPT, REJECT, UNCERTAIN),
}
REASON_CODES = tuple(sorted(REASON_CODE_VERDICTS))

JUDGE_INSTRUCTIONS = """You are a visual semantic fidelity judge.

Compare the provided image pixels with the visual intent expressed by the
supplied queryUsed (and assetPreference when present). Judge the pixels and the
intent only.

ACCEPT when the image sufficiently represents the main subject/intention, even
if it is approximate, generic, or does not include secondary details. Do not
require literal fidelity to every word of the query; coarse-but-usable images
must pass.

REJECT ONLY on a material mismatch, such as: the central entity or variant is
wrong; a visible factual contradiction; an essential action/relation is absent
and the image is misleading as a result; the requested content type was
replaced by something semantically different; or the image is essentially
unrelated to the concept.

UNCERTAIN only when there is not enough visual evidence to claim a material
mismatch.

Return the required structured verdict."""
JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": [ACCEPT, REJECT, UNCERTAIN]},
        "reasonCode": {"type": "string", "enum": REASON_CODES},
        "shortReason": {
            "type": "string",
            "minLength": 1,
            "maxLength": 180,
            "description": "one or two short sentences explaining the verdict",
        },
    },
    "required": ["verdict", "reasonCode", "shortReason"],
    "additionalProperties": False,
}


def _load_labels_checked(path: Path) -> list[dict]:
    labels = load_labels(path)
    summary = validate_labels(labels)
    if summary["total"] not in (38, 20):
        raise ValueError(f"expected 38 (canonical) or 20 (development) labels, got {summary['total']}")
    return labels


def _read_project_env() -> dict[str, str]:
    """Read simple project .env values without ever returning them to output."""
    values: dict[str, str] = {}
    path = _PROJECT_ROOT / ".env"
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_api_key() -> str | None:
    env = _read_project_env()
    return (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or env.get("OPENAI_API_KEY")
        or env.get("LLM_API_KEY")
    )


def _mime_type(path: Path) -> str:
    if path.suffix.lower() == ".jpg":
        return "image/jpeg"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _image_data_url(asset_path: Path) -> tuple[str, int | None]:
    """Return an in-memory data URL and GIF frame metadata, without mutation."""
    raw = asset_path.read_bytes()
    gif_frame: int | None = None
    if asset_path.suffix.lower() == ".gif":
        from PIL import Image

        with Image.open(BytesIO(raw)) as image:
            if getattr(image, "is_animated", False):
                image.seek(0)
                gif_frame = 0
                frame = image.convert("RGB")
                encoded = BytesIO()
                frame.save(encoded, format="PNG")
                raw = encoded.getvalue()
                mime = "image/png"
            else:
                mime = "image/gif"
    else:
        mime = _mime_type(asset_path)
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}", gif_frame


def _image_hash_from_data_url(data_url: str) -> str:
    """Compute SHA-256 of the effective image bytes from a data URL."""
    if not data_url.startswith("data:"):
        return hashlib.sha256(data_url.encode()).hexdigest()
    _, b64_payload = data_url.split(",", 1)
    payload_bytes = base64.b64decode(b64_payload)
    return hashlib.sha256(payload_bytes).hexdigest()


def load_asset_preference(entry: dict) -> str | None:
    """Resolve the assetPreference from the persisted segment contract.

    Reads ``data/videos/<jobId>/metadata.json`` and joins by sceneNumber /
    segmentIndex into ``script.scenes[].visualPlan.visualSequence[]``. Returns
    None when the contract is missing/unreadable/absent so the semantic input
    is simply dropped (the field is only sent when it is part of the contract).
    """
    job_id = entry.get("jobId", "")
    metadata = _PROJECT_ROOT / "data" / "videos" / job_id / "metadata.json"
    if not metadata.is_file():
        return None
    try:
        data = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    script = data.get("script") or {}
    scenes = script.get("scenes") or []
    scene_number = int(entry.get("sceneNumber", -1))
    segment_index = int(entry.get("segmentIndex", -1))
    for scene in scenes:
        if int(scene.get("sceneNumber", -1)) != scene_number:
            continue
        visual_plan = scene.get("visualPlan") or {}
        sequence = visual_plan.get("visualSequence") or []
        for segment in sequence:
            if int(segment.get("segmentIndex", -1)) == segment_index:
                value = segment.get("assetPreference")
                return value if isinstance(value, str) and value.strip() else None
    return None


def build_semantic_text(entry: dict) -> tuple[str, str | None]:
    """Build the judge semantic text and report whether assetPreference was used."""
    asset_preference = load_asset_preference(entry)
    text = f"Visual intent: {entry['queryUsed']}"
    if asset_preference:
        text += f"\nAsset preference: {asset_preference}"
    return text, asset_preference


def build_request(entry: dict) -> tuple[dict[str, Any], int | None, str, str | None]:
    """Build the exact request payload and a non-secret request fingerprint."""
    asset_path = _PROJECT_ROOT / entry["assetPath"]
    if not asset_path.is_file():
        raise FileNotFoundError(f"asset not found: {asset_path}")
    image_url, gif_frame = _image_data_url(asset_path)
    semantic_text, asset_preference = build_semantic_text(entry)
    request: dict[str, Any] = {
        "model": MODEL,
        "instructions": JUDGE_INSTRUCTIONS,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": semantic_text},
                    {
                        "type": "input_image",
                        "image_url": image_url,
                        "detail": DETAIL,
                    },
                ],
            }
        ],
        "reasoning": {"effort": REASONING_EFFORT},
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "visual_fidelity_verdict_v2",
                "strict": True,
                "schema": JUDGE_SCHEMA,
            }
        },
    }
    image_hash = _image_hash_from_data_url(image_url)
    fingerprint_request = {
        "model": MODEL,
        "instructions": JUDGE_INSTRUCTIONS,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": semantic_text},
                    {
                        "type": "input_image",
                        "image_url": image_hash,
                        "detail": DETAIL,
                    },
                ],
            }
        ],
        "reasoning": {"effort": REASONING_EFFORT},
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "visual_fidelity_verdict_v2",
                "strict": True,
                "schema": JUDGE_SCHEMA,
            }
        },
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_request, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return request, gif_frame, fingerprint, asset_preference


def _count_request(client: Any, request: dict[str, Any]) -> int:
    count_request = dict(request)
    count_request.pop("max_output_tokens", None)
    response = client.responses.input_tokens.count(**count_request)
    tokens = getattr(response, "input_tokens", None)
    if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
        raise ValueError(f"invalid input token count response: {tokens!r}")
    return tokens


def _cost(input_tokens: int, cached_tokens: int, output_tokens: int) -> float:
    cached = min(max(cached_tokens, 0), input_tokens)
    uncached = input_tokens - cached
    return (
        uncached * INPUT_PRICE_USD_PER_MILLION
        + cached * CACHED_INPUT_PRICE_USD_PER_MILLION
        + output_tokens * OUTPUT_PRICE_USD_PER_MILLION
    ) / 1_000_000


def _preflight_report(labels: list[dict], client: Any, output_path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_input = 0
    for entry in labels:
        request, gif_frame, fingerprint, asset_preference = build_request(entry)
        tokens = _count_request(client, request)
        total_input += tokens
        row: dict[str, Any] = {
            "assetPath": entry["assetPath"],
            "inputTokens": tokens,
            "requestFingerprint": fingerprint,
            "gifFrame": gif_frame,
            "assetPreference": asset_preference,
        }
        rows.append(row)
    projected_input = total_input * INPUT_PRICE_USD_PER_MILLION / 1_000_000
    projected_output = (
        len(labels) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE_USD_PER_MILLION / 1_000_000
    )
    projected_total = projected_input + projected_output
    report = {
        "status": "COST_BUDGET_EXCEEDED" if projected_total > MAX_TOTAL_COST_USD else "READY",
        "model": MODEL,
        "detail": DETAIL,
        "reasoningEffort": REASONING_EFFORT,
        "maxOutputTokens": MAX_OUTPUT_TOKENS,
        "promptSchemaVersion": PROMPT_SCHEMA_VERSION,
        "pricingReference": {
            "date": PRICING_REFERENCE_DATE,
            "inputUsdPerMillion": INPUT_PRICE_USD_PER_MILLION,
            "cachedInputUsdPerMillion": CACHED_INPUT_PRICE_USD_PER_MILLION,
            "outputUsdPerMillion": OUTPUT_PRICE_USD_PER_MILLION,
        },
        "maxTotalCostUsd": MAX_TOTAL_COST_USD,
        "assetCount": len(labels),
        "totalInputTokens": total_input,
        "projectedInputCostUsd": projected_input,
        "projectedMaxOutputCostUsd": projected_output,
        "projectedMaxTotalCostUsd": projected_total,
        "requests": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _value(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def parse_judge_output(raw: Any) -> dict[str, str]:
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"judge output is not valid JSON: {exc}") from exc
    elif isinstance(raw, dict):
        parsed = raw
    else:
        raise ValueError("structured output must be JSON text or an object")
    if not isinstance(parsed, dict):
        raise ValueError("judge output must be a JSON object")
    required = {"verdict", "reasonCode", "shortReason"}
    if set(parsed) != required:
        raise ValueError(
            f"structured output must contain exactly {sorted(required)}, "
            f"got {sorted(parsed)}"
        )
    verdict = parsed["verdict"]
    reason_code = parsed["reasonCode"]
    short_reason = parsed["shortReason"]
    if verdict not in (ACCEPT, REJECT, UNCERTAIN):
        raise ValueError(f"invalid verdict: {verdict!r}")
    if reason_code not in REASON_CODE_VERDICTS:
        raise ValueError(f"invalid reasonCode: {reason_code!r}")
    if verdict not in REASON_CODE_VERDICTS[reason_code]:
        raise ValueError(
            f"reasonCode {reason_code!r} is not allowed for verdict {verdict!r}"
        )
    if not isinstance(short_reason, str) or not short_reason.strip():
        raise ValueError("shortReason must be a non-empty string")
    if len(short_reason) > 180:
        raise ValueError(f"shortReason exceeds 180 characters ({len(short_reason)})")
    return {
        "verdict": verdict,
        "reasonCode": reason_code,
        "shortReason": short_reason[:180],
    }


def _response_output(response: Any) -> str:
    refusal = getattr(response, "refusal", None)
    if refusal:
        raise ValueError(f"model refusal: {refusal}")
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text
    raise ValueError("response contained no output_text")


def _usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    input_tokens = int(_value(usage, "input_tokens", 0) or 0)
    output_tokens = int(_value(usage, "output_tokens", 0) or 0)
    details = _value(usage, "input_tokens_details", {}) or {}
    output_details = _value(usage, "output_tokens_details", {}) or {}
    cached = int(_value(details, "cached_tokens", 0) or 0)
    reasoning = int(_value(output_details, "reasoning_tokens", 0) or 0)
    return {
        "inputTokens": input_tokens,
        "cachedInputTokens": cached,
        "outputTokens": output_tokens,
        "reasoningTokens": reasoning,
    }


def operational_verdict(verdict: str) -> str:
    """Fail-open mapping: UNCERTAIN becomes ACCEPT for operating metrics."""
    return ACCEPT if verdict == UNCERTAIN else verdict


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, math.ceil(0.95 * len(sorted_values)) - 1)
    return sorted_values[max(0, index)]


def _phase_report(
    labels: list[dict], results: list[dict], phase: str
) -> dict[str, Any]:
    raw_verdicts = {
        row["assetPath"]: row["verdict"]
        for row in results
        if "verdict" in row
    }
    raw_counts = Counter(raw_verdicts.values())
    metrics = None
    operational_verdicts: dict[str, str] = {}
    if len(raw_verdicts) == len(labels):
        operational_verdicts = {
            path: operational_verdict(verdict)
            for path, verdict in raw_verdicts.items()
        }
        metrics = evaluate_verdicts(labels, operational_verdicts)

    latencies = [row["latencySeconds"] for row in results]
    report: dict[str, Any] = {
        "phase": phase,
        "assetCount": len(labels),
        "verdictDistribution": {
            "ACCEPT": raw_counts.get(ACCEPT, 0),
            "REJECT": raw_counts.get(REJECT, 0),
            "UNCERTAIN": raw_counts.get(UNCERTAIN, 0),
        },
        "reasonCodeDistribution": dict(
            Counter(row["reasonCode"] for row in results if "reasonCode" in row)
        ),
        "operational": {
            "uncertainOperationalizedAsAccept": sum(
                1 for row in results if row.get("verdict") == UNCERTAIN
            ),
            "policy": "UNCERTAIN -> ACCEPT (fail-open)",
            "verdictsUsedForMetrics": operational_verdicts,
        },
        "benchmarkMetrics": metrics,
        "latency": {
            "medianSeconds": _median(latencies),
            "p95Seconds": _p95(latencies),
            "minSeconds": min(latencies) if latencies else None,
            "maxSeconds": max(latencies) if latencies else None,
        },
        "results": results,
    }
    return report


def execute_phase(
    labels: list[dict], client: Any, preflight: dict[str, Any], phase: str
) -> dict[str, Any]:
    if preflight.get("status") != "READY":
        raise RuntimeError("preflight did not authorize execution")
    if preflight.get("model") != MODEL or preflight.get("detail") != DETAIL:
        raise RuntimeError("preflight configuration does not match execution")
    rows_by_path = {row["assetPath"]: row for row in preflight["requests"]}
    results: list[dict[str, Any]] = []
    total_cost = 0.0
    for entry in labels:
        request, gif_frame, fingerprint, asset_preference = build_request(entry)
        preflight_row = rows_by_path.get(entry["assetPath"])
        if not preflight_row or preflight_row["requestFingerprint"] != fingerprint:
            raise RuntimeError(f"request changed after preflight: {entry['assetPath']}")
        started = time.monotonic()
        row: dict[str, Any] = {
            "assetPath": entry["assetPath"],
            "gifFrame": gif_frame,
            "assetPreference": asset_preference,
            "status": "ERROR",
        }
        try:
            response = client.responses.create(**request)
            usage = _usage(response)
            row.update(
                {
                    "status": str(getattr(response, "status", "completed")),
                    "usage": usage,
                    "costUsd": _cost(
                        usage["inputTokens"],
                        usage["cachedInputTokens"],
                        usage["outputTokens"],
                    ),
                }
            )
            row.update(parse_judge_output(_response_output(response)))
        except Exception as exc:  # independent asset failures are recorded
            row["errorType"] = type(exc).__name__
            row["error"] = str(exc)[:500]
        row["latencySeconds"] = time.monotonic() - started
        total_cost += float(row.get("costUsd", 0.0))
        results.append(row)
        if total_cost > MAX_TOTAL_COST_USD:
            raise RuntimeError("actual cost exceeded hard budget cap")
    report = _phase_report(labels, results, phase)
    report["status"] = (
        "COMPLETED" if all(r["status"] != "ERROR" for r in results) else "PARTIAL_FAILURE"
    )
    report["totalCostUsd"] = total_cost
    report["averageCostUsd"] = total_cost / len(results)
    return report


def _resolve_client() -> Any:
    api_key = resolve_api_key()
    if not api_key:
        raise RuntimeError("no OpenAI-compatible API key found")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "official openai SDK is unavailable; install it only in an isolated benchmark environment"
        ) from exc
    return OpenAI(api_key=api_key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluation-only visual fidelity judge V2 benchmark (gpt-5.6-luna, "
            "ACCEPT/REJECT/UNCERTAIN fail-open). Requires an explicit preflight."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--labels",
        default=str(_PROJECT_ROOT / "tests/fixtures/asset_visual_fidelity/labels.json"),
    )
    parser.add_argument(
        "--phase",
        default="canonical-38",
        help="phase label persisted in the report (default canonical-38)",
    )
    parser.add_argument(
        "--preflight-report",
        default=str(
            _PROJECT_ROOT
            / "data/evaluations/visual-fidelity-vlm-judge-v2/preflight.json"
        ),
    )
    parser.add_argument(
        "--output",
        default=str(
            _PROJECT_ROOT
            / "data/evaluations/visual-fidelity-vlm-judge-v2/results.json"
        ),
    )
    args = parser.parse_args(argv)
    try:
        labels = _load_labels_checked(Path(args.labels))
        client = _resolve_client()
        if args.preflight:
            report = _preflight_report(labels, client, Path(args.preflight_report))
            print(
                json.dumps(
                    {
                        k: report[k]
                        for k in (
                            "status",
                            "assetCount",
                            "totalInputTokens",
                            "projectedInputCostUsd",
                            "projectedMaxOutputCostUsd",
                            "projectedMaxTotalCostUsd",
                            "maxTotalCostUsd",
                        )
                    },
                    indent=2,
                )
            )
            return 0 if report["status"] == "READY" else 2
        preflight = json.loads(Path(args.preflight_report).read_text(encoding="utf-8"))
        result = execute_phase(labels, client, preflight, args.phase)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "status",
                        "phase",
                        "totalCostUsd",
                        "averageCostUsd",
                        "verdictDistribution",
                    )
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        print(
            json.dumps(
                {
                    "benchmarkMetrics": (
                        {
                            k: result["benchmarkMetrics"][k]
                            for k in (
                                "acceptableRetained",
                                "badRejected",
                                "falseAcceptances",
                                "falseRejections",
                                "confusionMatrix",
                            )
                        }
                        if result.get("benchmarkMetrics")
                        else None
                    )
                },
                indent=2,
            )
        )
        return 0 if result["status"] == "COMPLETED" else 3
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())