"""Optional visual-fidelity pixel gate — OpenCLIP ViT-B-32 (Slice 1, component only).

Second visual gate that evaluates downloaded image pixels against the primary
visual intent (``queryUsed``). The metadata gate
(``deterministic_anchor_coverage_v2``) remains the first cheap stage; this
module is NOT integrated into the executor/bridge yet.

Behavior contract:
  - Optional dependency: ``torch`` and ``open_clip`` are imported lazily inside
    functions only. Importing this module never imports them (nor PIL).
  - Model cache: OpenCLIP ``ViT-B-32`` / ``laion2b_s34b_b79k`` is loaded once
    per process, guarded by a lock (thread-safe). First load may fetch weights
    into the user cache (outside the repo); the repo never contains weights.
  - Device: CUDA if ``torch.cuda.is_available()`` else CPU; a device override
    is honored for testing.
  - Scoring: normalized cosine similarity (``encode_image`` vs ``encode_text``),
    batch=1, ``model.eval()`` + ``torch.no_grad()``. Identical to the Slice 2
    benchmark (GPU == CPU reproducibity already measured, <1e-6).
  - Text policy: P1 = raw ``queryUsed`` (no templates).
  - GIF: always evaluates frame 0, converted to RGB; the original file is
    never mutated (opened read-only in memory).
  - Threshold: NEVER hardcoded. ``0.2296`` is a benchmark calibration result,
    NOT a production default. The gate is activated only when
    ``VISUAL_FIDELITY_THRESHOLD`` is set to a finite number.
  - Statuses: ``DISABLED`` (no/invalid threshold, or activation gate off),
    ``UNAVAILABLE`` (torch/open_clip absent, model load failure, or scoring
    failure), ``SCORED`` (valid verdict). The component never raises: it is a
    fail-soft gate that the executor will either use or bypass explicitly.
"""

from __future__ import annotations

import math
import os
import threading
import time
from pathlib import Path
from typing import Any

ARCHITECTURE = "ViT-B-32"
PRETRAINED = "laion2b_s34b_b79k"
TEXT_POLICY = "p1"
METHOD = "openclip_vit_b32_p1"
GIF_FRAME = 0

THRESHOLD_ENV = "VISUAL_FIDELITY_THRESHOLD"

SCORED = "SCORED"
UNAVAILABLE = "UNAVAILABLE"
DISABLED = "DISABLED"

ACCEPT = "ACCEPT"
REJECT = "REJECT"
BYPASS = "BYPASS"

_backend: Any | None = None
_backend_error: str | None = None
_backend_lock = threading.Lock()


class _OpenClipBackend:
    """Minimal OpenCLIP wrapper: model + tokenizer + preprocess + device."""

    def __init__(self, model: Any, tokenizer: Any, preprocess: Any, device: str) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.preprocess = preprocess
        self.device = device

    def score(self, image: Any, text: str) -> float:
        """Normalized cosine similarity between the image and the text."""
        import torch

        text_tokens = self.tokenizer([text])
        with torch.no_grad():
            text_features = self.model.encode_text(text_tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
            image_features = self.model.encode_image(image_tensor)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            sim = image_features @ text_features.T
            return float(sim.item())


def _create_backend(device_override: str | None = None) -> _OpenClipBackend:
    """Create the OpenCLIP backend. Imports torch/open_clip lazily.

    Raises on import/load failure; the caller converts it to ``UNAVAILABLE``.
    """
    try:
        import open_clip
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "visual fidelity unavailable: torch/open_clip not installed "
            "(optional dependency; see openclip_vit_b32 extra)"
        ) from exc

    device = device_override or ("cuda" if torch.cuda.is_available() else "cpu")
    model, _, preprocess = open_clip.create_model_and_transforms(
        ARCHITECTURE, pretrained=PRETRAINED, device=device
    )
    model = model.eval()
    tokenizer = open_clip.get_tokenizer(ARCHITECTURE)
    return _OpenClipBackend(model=model, tokenizer=tokenizer, preprocess=preprocess, device=device)


def _get_backend() -> _OpenClipBackend | None:
    """Return the process-wide cached backend, loading it once (thread-safe).

    A failed load is cached too: subsequent candidates do not retry importing
    the optional stack (avoids 1 retry per candidate for a missing dependency).
    """
    global _backend, _backend_error
    if _backend is not None:
        return _backend
    with _backend_lock:
        if _backend is not None:
            return _backend
        if _backend_error is not None:
            return None
        try:
            _backend = _create_backend()
        except Exception as exc:  # noqa: BLE001 - fail-soft gate
            _backend_error = f"{type(exc).__name__}: {exc}"
            return None
        return _backend


def _reset_backend_cache() -> None:
    """Drop the cached backend/error. Test-only helper (private)."""
    global _backend, _backend_error
    _backend = None
    _backend_error = None


def _load_threshold() -> tuple[float | None, str | None]:
    """Read the configured threshold. (None, reason) when disabled/invalid."""
    raw = os.getenv(THRESHOLD_ENV, "").strip()
    if not raw:
        return None, f"{THRESHOLD_ENV} not set; pixel gate disabled"
    try:
        value = float(raw)
    except ValueError:
        return None, f"invalid {THRESHOLD_ENV}={raw!r}; pixel gate disabled"
    if not math.isfinite(value):
        return None, f"non-finite {THRESHOLD_ENV}={raw!r}; pixel gate disabled"
    return value, None


def _load_image(image_path: Path) -> tuple[Any, int | None]:
    """Load an image in memory; GIFs are pinned to frame 0 (file never mutated)."""
    from PIL import Image

    image = Image.open(image_path)
    gif_frame: int | None = None
    if getattr(image, "is_animated", False):
        image.seek(GIF_FRAME)
        gif_frame = GIF_FRAME
    return image.convert("RGB"), gif_frame


def score_visual_fidelity(image_path: str | Path, text: str) -> dict:
    """Score an image against ``text`` (P1 = queryUsed) with the pixel gate.

    Returns a dict with: status, method, architecture, pretrained, textPolicy,
    textUsed, threshold, score, verdict, device, gifFrame, reason, latencyMs.
    Never raises: DISABLED/UNAVAILABLE/SCORED cover all paths (fail-soft).
    """
    threshold, config_reason = _load_threshold()
    base = {
        "method": METHOD,
        "architecture": ARCHITECTURE,
        "pretrained": PRETRAINED,
        "textPolicy": TEXT_POLICY,
        "textUsed": text,
        "threshold": threshold,
    }
    if threshold is None:
        return {
            **base,
            "status": DISABLED,
            "score": None,
            "verdict": BYPASS,
            "device": None,
            "gifFrame": None,
            "reason": config_reason,
            "latencyMs": None,
        }

    backend = _get_backend()
    if backend is None:
        return {
            **base,
            "status": UNAVAILABLE,
            "score": None,
            "verdict": BYPASS,
            "device": None,
            "gifFrame": None,
            "reason": _backend_error or "visual fidelity backend unavailable",
            "latencyMs": None,
        }

    start = time.monotonic()
    try:
        image, gif_frame = _load_image(Path(image_path))
        score = backend.score(image, text)
    except Exception as exc:  # noqa: BLE001 - fail-soft gate
        return {
            **base,
            "status": UNAVAILABLE,
            "score": None,
            "verdict": BYPASS,
            "device": backend.device,
            "gifFrame": None,
            "reason": f"scoring failed: {type(exc).__name__}: {exc}",
            "latencyMs": round((time.monotonic() - start) * 1000),
        }
    latency_ms = round((time.monotonic() - start) * 1000)
    return {
        **base,
        "status": SCORED,
        "score": score,
        "verdict": ACCEPT if score >= threshold else REJECT,
        "device": backend.device,
        "gifFrame": gif_frame,
        "reason": None,
        "latencyMs": latency_ms,
    }