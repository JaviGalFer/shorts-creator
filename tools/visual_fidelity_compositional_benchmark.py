#!/usr/bin/env python3
"""Compositional visual fidelity benchmark — BLIP ITM vs OpenCLIP scoring.

EVALUATION-ONLY tool for ``visual-fidelity-compositional-benchmark``. It is NOT
production runtime: it lazy-imports the optional ML stack (torch / transformers
/ open_clip) and is meant to run inside an isolated benchmark virtualenv
outside the repository.

Behavior contract:
  - Reads a labels JSON (the canonical 38-asset calibration set or the fresh
    20-asset holdout) and scores each actual image from its ``assetPath``
    against the raw ``queryUsed`` (policy p1 only).
  - Supported models (benchmarked ONLY these):
      * blip_itm_base       -> Salesforce/blip-itm-base-coco (BLIP ITM head)
      * openclip_vit_b32    -> OpenCLIP ViT-B-32 laion2b_s34b_b79k (reference)
  - BLIP ITM uses transformers.BlipProcessor + BlipForImageTextRetrieval with
    ``use_itm_head=True``; the score is the softmax probability of the
    positive ITM class (``softmax(itm_score)[0, 0]``). OpenCLIP uses the
    normalized cosine similarity (image vs text embeddings).
  - GIF images: evaluates frame 0 (matches the human benchmark convention).
  - Deterministic eval mode (``eval()``, ``no_grad()``, fixed seed, batch=1).
  - Device: ``--device auto|cuda|cpu`` (auto prefers CUDA). VRAM is measured
    only on CUDA; RSS is always measured.
  - Never mutates image or metadata files. Writes a read-only scores JSON
    keyed by assetPath plus measured performance numbers.
  - No production threshold is defined anywhere here. Threshold calibration is
    done by ``tools/visual_fidelity_benchmark.py`` on the 38 calibration set
    only; the holdout is NEVER used to select a threshold.
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
_TOOLS = str(_PROJECT_ROOT / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from visual_fidelity_benchmark import load_labels  # noqa: E402

MODELS = ("blip_itm_base", "openclip_vit_b32")

BLIP_CHECKPOINT = "Salesforce/blip-itm-base-coco"
OPENCLIP_ARCH = "ViT-B-32"
OPENCLIP_PRETRAINED = "laion2b_s34b_b79k"

GIF_FRAME = 0
_POLICY_TEMPLATE = "{queryUsed}"


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


def _resolve_device(name: str) -> str:
    if name == "auto":
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    if name in ("cuda", "cpu"):
        return name
    raise ValueError(f"unknown device {name!r}; expected auto|cuda|cpu")


def _blip_score(model, processor, text: str, image_path: Path, device: str) -> tuple[float, float]:
    """Score one image vs one raw text with the BLIP ITM head at batch=1."""
    import torch

    image = _load_image(image_path)
    batch = processor(
        text=[text],
        images=[image],
        padding="max_length",
        return_tensors="pt",
    ).to(device)
    start = time.monotonic()
    with torch.no_grad():
        outputs = model(**batch, use_itm_head=True)
        logits = outputs.itm_score  # shape (batch, 2): [itm, not_itm]
        prob = torch.softmax(logits.float(), dim=-1)[0, 0].item()
    latency = time.monotonic() - start
    return float(prob), latency


def _openclip_score(
    model, tokenizer, preprocess, text_tokens, image_path: Path, device: str
) -> tuple[float, float]:
    """Score one image vs a pre-tokenized text at batch=1."""
    import torch

    image = preprocess(_load_image(image_path)).unsqueeze(0)
    if device == "cuda":
        image = image.to(device)
    start = time.monotonic()
    with torch.no_grad():
        image_features = model.encode_image(image)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        sim = (image_features @ text_tokens.unsqueeze(-1)).item()
    latency = time.monotonic() - start
    return float(sim), latency


def _load_blip(device: str) -> tuple[Any, dict]:
    import torch
    from transformers import BlipForImageTextRetrieval, BlipProcessor

    processor = BlipProcessor.from_pretrained(BLIP_CHECKPOINT)
    model = BlipForImageTextRetrieval.from_pretrained(BLIP_CHECKPOINT)
    if device == "cuda":
        model = model.to(device)
    model.eval()
    torch.manual_seed(0)
    backend = {
        "kind": "blip_itm",
        "architecture": "BLIP base",
        "pretrained": BLIP_CHECKPOINT,
        "model": model,
        "processor": processor,
        "device": device,
    }
    versions = {"transformers": importlib.metadata.version("transformers")}
    return backend, versions


def _load_openclip(device: str) -> tuple[Any, dict]:
    import open_clip
    import torch

    model, _, preprocess = open_clip.create_model_and_transforms(
        OPENCLIP_ARCH, pretrained=OPENCLIP_PRETRAINED, device="cpu"
    )
    if device == "cuda":
        model = model.to(device)
    model = model.eval()
    tokenizer = open_clip.get_tokenizer(OPENCLIP_ARCH)
    torch.manual_seed(0)
    backend = {
        "kind": "openclip",
        "architecture": OPENCLIP_ARCH,
        "pretrained": OPENCLIP_PRETRAINED,
        "model": model,
        "tokenizer": tokenizer,
        "preprocess": preprocess,
        "device": device,
    }
    versions = {"open_clip_torch": importlib.metadata.version("open_clip_torch")}
    if device == "cuda":
        versions["timm"] = importlib.metadata.version("timm")
    return backend, versions


def _load_model(model: str, device: str) -> tuple[Any, dict]:
    if model == "blip_itm_base":
        return _load_blip(device)
    if model == "openclip_vit_b32":
        return _load_openclip(device)
    raise ValueError(f"unknown model {model!r}; supported: {', '.join(MODELS)}")


def _score_all(labels: list[dict], model: str, device: str) -> dict[str, Any]:
    import torch

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
        texts.append(_POLICY_TEMPLATE.format(queryUsed=entry["queryUsed"]))

    load_start = time.monotonic()
    backend, versions = _load_model(model, device)
    load_time = time.monotonic() - load_start

    cuda_after_load: dict[str, float] | None = None
    if device == "cuda":
        cuda_after_load = _cuda_memory_stats()

    scoring_start = time.monotonic()
    per_image_latencies: list[float] = []
    scores: dict[str, float] = {}
    logits: dict[str, float] | None = {} if backend["kind"] == "blip_itm" else None

    if backend["kind"] == "openclip":
        text_tokens = backend["tokenizer"](texts)
        if device == "cuda":
            text_tokens = text_tokens.to(device)
        with torch.no_grad():
            text_features = backend["model"].encode_text(text_tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        for i, (entry, image_path) in enumerate(zip(entries, image_paths)):
            score, latency = _openclip_score(
                backend["model"], backend["tokenizer"], backend["preprocess"],
                text_features[i], image_path, device,
            )
            per_image_latencies.append(latency)
            scores[entry["assetPath"]] = score
    else:
        for entry, image_path in zip(entries, image_paths):
            text = _POLICY_TEMPLATE.format(queryUsed=entry["queryUsed"])
            prob, latency = _blip_score(
                backend["model"], backend["processor"], text, image_path, device
            )
            per_image_latencies.append(latency)
            scores[entry["assetPath"]] = prob
    total_scoring_time = time.monotonic() - scoring_start

    cuda_after_scoring: dict[str, float] | None = None
    if device == "cuda":
        cuda_after_scoring = _cuda_memory_stats(peak=True, reset=True)

    latencies_sorted = sorted(per_image_latencies)
    versions["torch"] = importlib.metadata.version("torch")
    versions["Pillow"] = importlib.metadata.version("Pillow")

    result = {
        "model": model,
        "architecture": backend["architecture"],
        "pretrained": backend["pretrained"],
        "policy": "p1",
        "policyTemplate": _POLICY_TEMPLATE,
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
            "cuda": cuda_after_scoring,
            "cudaAfterLoadMiB": cuda_after_load,
        },
        "scores": scores,
    }
    if logits is not None:
        result["itmLogits"] = logits
    return result


def _cuda_memory_stats(*, peak: bool = False, reset: bool = False) -> dict[str, float]:
    import torch

    stats: dict[str, float] = {
        "maxMemoryAllocatedMiB": torch.cuda.max_memory_allocated() / (1024**2),
        "maxMemoryReservedMiB": torch.cuda.max_memory_reserved() / (1024**2),
    }
    if peak:
        stats["maxMemoryPeakAllocatedMiB"] = torch.cuda.max_memory_allocated() / (1024**2)
    if reset:
        torch.cuda.reset_peak_memory_stats()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluation-only compositional visual fidelity benchmark: BLIP ITM "
            "(Salesforce/blip-itm-base-coco) with use_itm_head=True vs OpenCLIP "
            "ViT-B-32 over a labeled asset set (calibration or holdout)."
        )
    )
    parser.add_argument(
        "--labels",
        required=True,
        help="Path to the labels JSON (canonical 38 or fresh 20 holdout)",
    )
    parser.add_argument(
        "--model",
        required=True,
        choices=MODELS,
        help="Model to score with",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=("auto", "cuda", "cpu"),
        help="Device: auto (prefer CUDA), cuda, or cpu",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output path for the scores JSON (ignored data dir recommended)",
    )
    args = parser.parse_args(argv)

    labels = load_labels(Path(args.labels))
    if not labels:
        print("ERROR: labels file contains no entries", file=sys.stderr)
        return 1

    device = _resolve_device(args.device)
    if device == "cuda":
        import torch

        if not torch.cuda.is_available():
            print(
                f"ERROR: device {args.device!r} requested but CUDA is unavailable",
                file=sys.stderr,
            )
            return 1
        print(f"cuda device: {torch.cuda.get_device_name(0)}", file=sys.stderr)

    try:
        result = _score_all(labels, args.model, device)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=False),
        encoding="utf-8",
    )
    perf = result["performance"]
    print(f"wrote {out}")
    print(
        f"model={args.model} device={result['device']} count={result['count']} "
        f"load={perf['loadTimeSeconds']:.2f}s "
        f"total={perf['totalScoringTimeSeconds']:.2f}s "
        f"median={perf['candidateLatencyMedianSeconds'] * 1000:.1f}ms "
        f"p95={perf['candidateLatencyP95Seconds'] * 1000:.1f}ms "
        f"rss={perf['peakRssMiB']:.0f}MiB"
    )
    if perf.get("cuda"):
        print(
            f"vrma={perf['cuda']['maxMemoryAllocatedMiB']:.1f}MiB "
            f"peak={perf['cuda'].get('maxMemoryPeakAllocatedMiB', float('nan')):.1f}MiB",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())