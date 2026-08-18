#!/usr/bin/env python3
"""Local image-text encoder benchmark for asset-visual-semantic-fidelity (Slice 2).

EVALUATION-ONLY tool. It is NOT production runtime: it lazy-imports the
optional ML stack (torch / open_clip_torch / transformers) and is meant to run
inside an isolated benchmark virtualenv outside the repository.

Behavior contract:
  - Reads the canonical labels JSON and scores each of the 38 actual images
    from its ``assetPath`` against one of two predetermined text policies.
  - Supported models (benchmarked ONLY these):
      * openclip_vit_b32   -> OpenCLIP ViT-B-32, pretrained laion2b_s34b_b79k
      * siglip2_base       -> google/siglip2-base-patch16-224 (transformers)
  - Text policies (exact, no template tuning):
      * p1: the raw queryUsed
      * p2: "an image depicting: {queryUsed}"
  - GIF images: explicitly evaluates frame 0 (matches the human benchmark, in
    which the first frame of the aurora GIF was classified
    FALSE_POSITIVE_OR_UNUSABLE).
  - Native image-text similarity per model (documented behavior; scores of
    different models are NOT comparable across numeric scales):
      * OpenCLIP: normalized cosine similarity (encode_image vs encode_text).
      * SigLIP2:  sigmoid(logits_per_image) from the joint forward pass.
  - Deterministic eval mode (eval(), no_grad(), fixed seed, batch=1).
  - Never mutates image or metadata files. Writes a read-only scores JSON
    keyed by assetPath plus measured CPU performance numbers.
  - No production threshold is defined anywhere here.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import resource
import sys
import time
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

TEXT_POLICIES: dict[str, str] = {
    "p1": "{queryUsed}",
    "p2": "an image depicting: {queryUsed}",
}

MODELS = ("openclip_vit_b32", "siglip2_base")

# GIFs must be evaluated at their first frame, matching the human benchmark.
GIF_FRAME = 0


def _load_labels(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("labels"), list):
        return data["labels"]
    if isinstance(data, list):
        return data
    raise ValueError(f"{path}: expected a JSON array or an object with a 'labels' array")


def _load_image(image_path: Path):
    """Load a PIL image, forcing GIFs to frame 0."""
    from PIL import Image

    img = Image.open(image_path)
    if getattr(img, "is_animated", False):
        img.seek(GIF_FRAME)
    return img.convert("RGB")


def _peak_rss_mib() -> float:
    try:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # KiB on Linux
        return rss / 1024.0
    except (AttributeError, ValueError):
        return float("nan")


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    index = min(len(sorted_values) - 1, math.ceil(q * len(sorted_values)) - 1)
    return sorted_values[max(0, index)]


def _score_image_openclip(model, tokenizer, preprocess, text_tokens, image_path: Path) -> tuple[float, float]:
    """Score one image vs a pre-tokenized text at batch=1; returns (score, latency)."""
    import torch

    image = preprocess(_load_image(image_path)).unsqueeze(0)
    start = time.monotonic()
    with torch.no_grad():
        image_features = model.encode_image(image)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        sim = (image_features @ text_tokens.unsqueeze(-1)).item()
    latency = time.monotonic() - start
    return float(sim), latency


def _score_image_siglip2(model, processor, text, image_path: Path) -> tuple[float, float]:
    """Score one image vs one text at batch=1; returns (score, latency)."""
    import torch

    image = _load_image(image_path)
    batch = processor(
        text=[text],
        images=[image],
        padding="max_length",
        return_tensors="pt",
    )
    start = time.monotonic()
    with torch.no_grad():
        logits = model(**batch).logits_per_image
        score = torch.sigmoid(logits).item()
    latency = time.monotonic() - start
    return float(score), latency


def _load_model(model: str) -> tuple[Any, dict]:
    """Load the selected model. Returns (backend, versions dict)."""
    if model == "openclip_vit_b32":
        import open_clip
        import torch

        model_obj, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k", device="cpu"
        )
        model_obj = model_obj.eval()
        tokenizer = open_clip.get_tokenizer("ViT-B-32")
        torch.manual_seed(0)
        backend = {
            "kind": "openclip",
            "architecture": "ViT-B-32",
            "pretrained": "laion2b_s34b_b79k",
            "model": model_obj,
            "tokenizer": tokenizer,
            "preprocess": preprocess,
            "device": "cpu",
        }
        return backend, {"open_clip_torch": importlib.metadata.version("open_clip_torch")}

    if model == "siglip2_base":
        import torch
        from transformers import AutoModel, AutoProcessor

        checkpoint = "google/siglip2-base-patch16-224"
        processor = AutoProcessor.from_pretrained(checkpoint)
        model_obj = AutoModel.from_pretrained(checkpoint).eval()
        torch.manual_seed(0)
        backend = {
            "kind": "siglip2",
            "architecture": "ViT-B/16",
            "pretrained": checkpoint,
            "model": model_obj,
            "processor": processor,
            "device": "cpu",
        }
        return backend, {"transformers": importlib.metadata.version("transformers")}

    raise ValueError(f"unknown model {model!r}; supported: {', '.join(MODELS)}")


def _score_all(
    labels: list[dict],
    model: str,
    policy: str,
) -> dict[str, Any]:
    template = TEXT_POLICIES[policy]
    entries = sorted(labels, key=lambda e: e["assetPath"])  # deterministic order

    image_paths: list[Path] = []
    texts: list[str] = []
    for entry in entries:
        image_path = _PROJECT_ROOT / entry["assetPath"]
        if not image_path.exists():
            raise FileNotFoundError(
                f"asset not found: {image_path} (required for the local benchmark)"
            )
        image_paths.append(image_path)
        texts.append(template.format(queryUsed=entry["queryUsed"]))

    load_start = time.monotonic()
    backend, versions = _load_model(model)
    load_time = time.monotonic() - load_start

    scoring_start = time.monotonic()
    per_image_latencies: list[float] = []
    scores: dict[str, float] = {}

    if backend["kind"] == "openclip":
        import torch

        text_tokens = backend["tokenizer"](texts)
        with torch.no_grad():
            text_features = backend["model"].encode_text(text_tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        for i, (entry, image_path) in enumerate(zip(entries, image_paths)):
            score, latency = _score_image_openclip(
                backend["model"], backend["tokenizer"], backend["preprocess"],
                text_features[i],
                image_path,
            )
            per_image_latencies.append(latency)
            scores[entry["assetPath"]] = score
    else:
        for entry, image_path in zip(entries, image_paths):
            text = template.format(queryUsed=entry["queryUsed"])
            score, latency = _score_image_siglip2(
                backend["model"], backend["processor"], text, image_path
            )
            per_image_latencies.append(latency)
            scores[entry["assetPath"]] = score
    total_scoring_time = time.monotonic() - scoring_start

    latencies_sorted = sorted(per_image_latencies)
    versions["torch"] = importlib.metadata.version("torch")
    if backend["kind"] == "openclip":
        versions["timm"] = importlib.metadata.version("timm")
    versions["Pillow"] = importlib.metadata.version("Pillow")

    return {
        "model": model,
        "architecture": backend["architecture"],
        "pretrained": backend["pretrained"],
        "policy": policy,
        "policyTemplate": template,
        "device": backend["device"],
        "packages": versions,
        "gifFrame": GIF_FRAME,
        "count": len(entries),
        "performance": {
            "loadTimeSeconds": load_time,
            "totalScoringTimeSeconds": total_scoring_time,
            "candidateLatencyMedianSeconds": _percentile(latencies_sorted, 0.5),
            "candidateLatencyP95Seconds": _percentile(latencies_sorted, 0.95),
            "candidateLatencyMinSeconds": _percentile(latencies_sorted, 0.0),
            "candidateLatencyMaxSeconds": _percentile(latencies_sorted, 1.0),
            "peakRssMiB": _peak_rss_mib(),
            "measurement": "CPU measured in Slice 2; provisional Plan estimates "
                           "are NOT persisted as measured facts",
        },
        "scores": scores,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluation-only local image-text encoder benchmark over the "
            "canonical 38-asset labeled dataset (Slice 2, CPU-first)."
        )
    )
    parser.add_argument(
        "--labels",
        default=str(_PROJECT_ROOT / "tests/fixtures/asset_visual_fidelity/labels.json"),
        help="Path to the canonical labels JSON",
    )
    parser.add_argument(
        "--model",
        required=True,
        choices=MODELS,
        help="Local encoder to benchmark",
    )
    parser.add_argument(
        "--policy",
        required=True,
        choices=tuple(TEXT_POLICIES),
        help="Text policy: p1 (raw queryUsed) or p2 (an image depicting: ...)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output path for the scores JSON (ignored data dir recommended)",
    )
    args = parser.parse_args(argv)

    labels = _load_labels(Path(args.labels))
    if len(labels) != 38:
        print(f"ERROR: expected 38 labels, got {len(labels)}", file=sys.stderr)
        return 1

    result = _score_all(labels, args.model, args.policy)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=False),
        encoding="utf-8",
    )
    print(f"wrote {out}")
    print(
        f"model={args.model} policy={args.policy} count={result['count']} "
        f"load={result['performance']['loadTimeSeconds']:.2f}s "
        f"total={result['performance']['totalScoringTimeSeconds']:.2f}s "
        f"p95={result['performance']['candidateLatencyP95Seconds']:.3f}s "
        f"rss={result['performance']['peakRssMiB']:.0f}MiB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
