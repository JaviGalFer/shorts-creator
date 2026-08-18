#!/usr/bin/env python3
"""Evaluation-only OpenAI multimodal benchmark for Slice 3A.

This tool is deliberately outside the production runtime. It uses the official
OpenAI Python SDK lazily, sends one independent Responses API request per
asset, and requires an explicit preflight before execution.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import mimetypes
import os
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = str(_ROOT / "tools")
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
MAX_TOTAL_COST_USD = 0.25
INPUT_PRICE_USD_PER_MILLION = 0.20
CACHED_INPUT_PRICE_USD_PER_MILLION = 0.02
OUTPUT_PRICE_USD_PER_MILLION = 1.20
PRICING_REFERENCE_DATE = "2026-08-18"
PROMPT_SCHEMA_VERSION = "slice3a-judge-v1"

REASON_CODES = (
    "MATCH",
    "WRONG_ENTITY",
    "WRONG_VARIANT_OR_ERA",
    "WRONG_ACTION_OR_SCENE",
    "TOO_GENERIC_OR_ADJACENT",
    "VISUALLY_UNUSABLE",
    "OTHER_MISMATCH",
)

JUDGE_INSTRUCTIONS = """You are a visual semantic fidelity judge.

Compare the image pixels with the visual intent expressed by the supplied
queryUsed. ACCEPT when the image clearly represents that intent or is
coarse-but-usable for it. REJECT when it is not sufficiently appropriate,
including a wrong entity, incompatible variant or era when relevant, wrong
action or scene, only tangentially related content, or visually unusable or
empty content. Do not require perfect editorial fidelity. Judge the pixels and
query only. Return only the required structured verdict."""

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": [ACCEPT, REJECT]},
        "reasonCode": {"type": "string", "enum": list(REASON_CODES)},
    },
    "required": ["verdict", "reasonCode"],
    "additionalProperties": False,
}


def _load_labels_checked(path: Path) -> list[dict]:
    labels = load_labels(path)
    summary = validate_labels(labels)
    if summary["total"] != 38:
        raise ValueError(f"expected canonical 38 labels, got {summary['total']}")
    return labels


def _read_project_env() -> dict[str, str]:
    """Read simple project .env values without ever returning them to output."""
    values: dict[str, str] = {}
    path = _ROOT / ".env"
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
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY") or env.get(
        "OPENAI_API_KEY"
    ) or env.get("LLM_API_KEY")


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
    # format: data:{mime};base64,{base64_payload}
    _, b64_payload = data_url.split(",", 1)
    payload_bytes = base64.b64decode(b64_payload)
    return hashlib.sha256(payload_bytes).hexdigest()


def build_request(entry: dict) -> tuple[dict[str, Any], int | None, str]:
    """Build the exact request payload and a non-secret request fingerprint."""
    asset_path = _ROOT / entry["assetPath"]
    if not asset_path.is_file():
        raise FileNotFoundError(f"asset not found: {asset_path}")
    image_url, gif_frame = _image_data_url(asset_path)
    request: dict[str, Any] = {
        "model": MODEL,
        "instructions": JUDGE_INSTRUCTIONS,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": entry["queryUsed"]},
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
                "name": "visual_fidelity_judgment",
                "strict": True,
                "schema": JUDGE_SCHEMA,
            }
        },
    }
    image_hash = _image_hash_from_data_url(image_url)
    fingerprint_request = dict(request)
    fingerprint_request["input"] = json.loads(json.dumps(request["input"]))
    fingerprint_request["input"][0]["content"][1]["image_url"] = image_hash
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_request, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return request, gif_frame, fingerprint


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


def _preflight_report(
    labels: list[dict], client: Any, output_path: Path
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_input = 0
    for entry in labels:
        request, gif_frame, fingerprint = build_request(entry)
        tokens = _count_request(client, request)
        total_input += tokens
        rows.append(
            {
                "assetPath": entry["assetPath"],
                "inputTokens": tokens,
                "requestFingerprint": fingerprint,
                "gifFrame": gif_frame,
            }
        )
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
        parsed = json.loads(raw)
    elif isinstance(raw, dict):
        parsed = raw
    else:
        raise ValueError("structured output must be JSON text or an object")
    if not isinstance(parsed, dict) or set(parsed) != {"verdict", "reasonCode"}:
        raise ValueError("structured output must contain exactly verdict and reasonCode")
    if parsed["verdict"] not in (ACCEPT, REJECT):
        raise ValueError(f"invalid verdict: {parsed['verdict']!r}")
    if parsed["reasonCode"] not in REASON_CODES:
        raise ValueError(f"invalid reasonCode: {parsed['reasonCode']!r}")
    return {"verdict": parsed["verdict"], "reasonCode": parsed["reasonCode"]}


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


def execute(
    labels: list[dict], client: Any, preflight: dict[str, Any]
) -> dict[str, Any]:
    if preflight.get("status") != "READY":
        raise RuntimeError("preflight did not authorize execution")
    if preflight.get("model") != MODEL or preflight.get("detail") != DETAIL:
        raise RuntimeError("preflight configuration does not match execution")
    rows_by_path = {row["assetPath"]: row for row in preflight["requests"]}
    results: list[dict[str, Any]] = []
    total_cost = 0.0
    for entry in labels:
        request, gif_frame, fingerprint = build_request(entry)
        preflight_row = rows_by_path.get(entry["assetPath"])
        if not preflight_row or preflight_row["requestFingerprint"] != fingerprint:
            raise RuntimeError(f"request changed after preflight: {entry['assetPath']}")
        started = time.monotonic()
        row: dict[str, Any] = {
            "assetPath": entry["assetPath"],
            "gifFrame": gif_frame,
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
    benchmark_metrics = None
    per_topic_metrics: dict[str, Any] = {}
    if all("verdict" in row for row in results):
        benchmark_metrics = aggregate_metrics(labels, results)
        grouped: dict[str, list[dict]] = defaultdict(list)
        for entry in labels:
            grouped[entry["topic"]].append(entry)
        for topic, topic_labels in grouped.items():
            topic_paths = {entry["assetPath"] for entry in topic_labels}
            topic_results = [row for row in results if row["assetPath"] in topic_paths]
            topic_verdicts = {
                row["assetPath"]: row["verdict"] for row in topic_results
            }
            per_topic_metrics[topic] = evaluate_verdicts(
                topic_labels, topic_verdicts
            )
    return {
        "status": "COMPLETED" if all(r["status"] != "ERROR" for r in results) else "PARTIAL_FAILURE",
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
        "assetCount": len(labels),
        "results": results,
        "benchmarkMetrics": benchmark_metrics,
        "perTopicMetrics": per_topic_metrics,
        "totalCostUsd": total_cost,
        "averageCostUsd": total_cost / len(labels),
    }


def aggregate_metrics(labels: list[dict], results: list[dict]) -> dict[str, Any]:
    verdicts = {r["assetPath"]: r["verdict"] for r in results if "verdict" in r}
    if len(verdicts) != len(labels):
        raise ValueError("cannot calculate benchmark metrics with missing verdicts")
    return evaluate_verdicts(labels, verdicts)


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
    parser = argparse.ArgumentParser(description="Slice 3A gpt-5.6-luna visual fidelity benchmark")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--labels", default=str(_ROOT / "tests/fixtures/asset_visual_fidelity/labels.json"))
    parser.add_argument(
        "--preflight-report",
        default=str(_ROOT / "data/evaluations/asset-visual-semantic-fidelity/gpt-5.6-luna-preflight.json"),
    )
    parser.add_argument(
        "--output",
        default=str(_ROOT / "data/evaluations/asset-visual-semantic-fidelity/gpt-5.6-luna-results.json"),
    )
    args = parser.parse_args(argv)
    labels = _load_labels_checked(Path(args.labels))
    try:
        client = _resolve_client()
        if args.preflight:
            report = _preflight_report(labels, client, Path(args.preflight_report))
            print(json.dumps({k: report[k] for k in (
                "status", "totalInputTokens", "projectedInputCostUsd",
                "projectedMaxOutputCostUsd", "projectedMaxTotalCostUsd",
            )}, indent=2))
            return 0 if report["status"] == "READY" else 2
        preflight = json.loads(Path(args.preflight_report).read_text(encoding="utf-8"))
        result = execute(labels, client, preflight)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({k: result[k] for k in ("status", "totalCostUsd", "averageCostUsd")}, indent=2))
        return 0 if result["status"] == "COMPLETED" else 3
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
