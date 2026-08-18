"""Focused tests for the visual fidelity pixel gate (Slice 1 component + Slice 2 integration).

Never imports torch/open_clip, never downloads weights, never touches the
network, never runs real model inference. Backends are faked; the only
third-party module exercised is PIL (already a test-suite dependency) for
synthetic images/GIFs. Executor/bridge integration is covered by mocking the
scorer and provider search/download functions.
"""

from __future__ import annotations

import ast
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

import shorts_creator.assets.visual_fidelity as vf

_MODULE_PATH = Path(vf.__file__).resolve()
THRESHOLD = vf.THRESHOLD_ENV


# ── Fixtures / helpers ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    vf._reset_backend_cache()
    monkeypatch.delenv(THRESHOLD, raising=False)
    yield
    vf._reset_backend_cache()


def _write_image(path: Path, color: tuple[int, int, int] = (120, 40, 10)) -> Path:
    Image.new("RGB", (4, 3), color).save(path, format="PNG")
    return path


def _write_gif(
    path: Path,
    first: tuple[int, int, int] = (255, 0, 0),
    second: tuple[int, int, int] = (0, 0, 255),
) -> Path:
    a = Image.new("RGB", (4, 3), first)
    b = Image.new("RGB", (4, 3), second)
    a.save(path, save_all=True, append_images=[b], duration=10, loop=0)
    return path


class _FakeBackend:
    """Minimal scored backend with a constant score and recording of inputs."""

    def __init__(self, score: float = 0.3, device: str = "cpu") -> None:
        self.score_value = score
        self.device = device
        self.seen_pixels: list[tuple[int, int, int]] = []
        self.seen_texts: list[str] = []

    def score(self, image: Any, text: str) -> float:
        self.seen_pixels.append(image.getpixel((0, 0)))  # type: ignore[attr-defined]
        self.seen_texts.append(text)
        return self.score_value


def _without_latency(result: dict) -> dict:
    out = dict(result)
    out.pop("latencyMs")
    return out


# ── Config / status ────────────────────────────────────────────────────────────


def test_no_threshold_disables_gate(monkeypatch, tmp_path):
    monkeypatch.setenv(THRESHOLD, "")
    result = vf.score_visual_fidelity(_write_image(tmp_path / "a.png"), "some query")
    assert result["status"] == vf.DISABLED
    assert result["verdict"] == vf.BYPASS
    assert result["score"] is None
    assert result["threshold"] is None
    assert THRESHOLD in result["reason"]
    assert result["device"] is None


def test_invalid_or_nonfinite_threshold_disables_gate(monkeypatch, tmp_path):
    img = _write_image(tmp_path / "a.png")
    for raw in ("not-a-number", "nan", "inf", "-inf"):
        monkeypatch.setenv(THRESHOLD, raw)
        result = vf.score_visual_fidelity(img, "some query")
        assert result["status"] == vf.DISABLED, raw
        assert result["verdict"] == vf.BYPASS
        assert result["score"] is None


def test_disabled_does_not_touch_backend(monkeypatch, tmp_path):
    def factory():  # pragma: no cover - must never be called
        raise AssertionError("backend must not load when the gate is disabled")

    monkeypatch.setattr(vf, "_create_backend", factory)
    result = vf.score_visual_fidelity(_write_image(tmp_path / "a.png"), "q")
    assert result["status"] == vf.DISABLED


def test_scoring_failure_is_unavailable(monkeypatch, tmp_path):
    class _BrokenBackend:
        device = "cpu"

        def score(self, image, text):
            raise OSError("decode error")

    monkeypatch.setattr(vf, "_create_backend", lambda: _BrokenBackend())
    monkeypatch.setenv(THRESHOLD, "0.25")
    result = vf.score_visual_fidelity(_write_image(tmp_path / "a.png"), "q")
    assert result["status"] == vf.UNAVAILABLE
    assert result["verdict"] == vf.BYPASS
    assert "decode error" in result["reason"]
    assert result["score"] is None


# ── UNAVAILABLE paths ──────────────────────────────────────────────────────────


def test_unavailable_when_backend_load_raises(monkeypatch, tmp_path):
    def factory():
        raise RuntimeError("no open_clip")

    monkeypatch.setattr(vf, "_create_backend", factory)
    monkeypatch.setenv(THRESHOLD, "0.25")
    result = vf.score_visual_fidelity(_write_image(tmp_path / "a.png"), "q")
    assert result["status"] == vf.UNAVAILABLE
    assert result["verdict"] == vf.BYPASS
    assert result["reason"]
    assert result["score"] is None


def test_unavailable_when_optional_deps_missing(monkeypatch, tmp_path):
    import importlib.util

    if importlib.util.find_spec("torch") or importlib.util.find_spec("open_clip_torch"):
        pytest.skip("optional ML stack installed; real missing-dependency path not reproducible here")
    monkeypatch.setenv(THRESHOLD, "0.25")
    result = vf.score_visual_fidelity(_write_image(tmp_path / "a.png"), "q")
    assert result["status"] == vf.UNAVAILABLE
    assert result["verdict"] == vf.BYPASS


def test_missing_image_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(vf, "_create_backend", lambda: _FakeBackend(device="cpu"))
    monkeypatch.setenv(THRESHOLD, "0.25")
    result = vf.score_visual_fidelity(tmp_path / "does-not-exist.png", "q")
    assert result["status"] == vf.UNAVAILABLE
    assert "FileNotFoundError" in result["reason"]


# ── Singleton / lazy lifecycle ─────────────────────────────────────────────────


def test_backend_loaded_exactly_once(monkeypatch, tmp_path):
    calls: list[int] = []
    monkeypatch.setattr(vf, "_create_backend", lambda: (calls.append(1) or _FakeBackend(device="cpu")))
    monkeypatch.setenv(THRESHOLD, "0.25")
    img = _write_image(tmp_path / "a.png")
    for query in ("first", "second", "third"):
        assert vf.score_visual_fidelity(img, query)["status"] == vf.SCORED
    assert len(calls) == 1


def test_failed_load_is_cached_not_retried(monkeypatch, tmp_path):
    calls: list[int] = []
    def factory():
        calls.append(1)
        raise RuntimeError("boom")

    monkeypatch.setattr(vf, "_create_backend", factory)
    monkeypatch.setenv(THRESHOLD, "0.25")
    img = _write_image(tmp_path / "a.png")
    assert vf.score_visual_fidelity(img, "q1")["status"] == vf.UNAVAILABLE
    assert vf.score_visual_fidelity(img, "q2")["status"] == vf.UNAVAILABLE
    assert len(calls) == 1


def test_thread_safe_singleton(monkeypatch, tmp_path):
    calls: list[int] = []
    lock = threading.Lock()

    def factory():
        with lock:
            calls.append(1)
        return _FakeBackend(score=0.3, device="cpu")

    monkeypatch.setattr(vf, "_create_backend", factory)
    monkeypatch.setenv(THRESHOLD, "0.25")
    img = _write_image(tmp_path / "a.png")
    results: list[dict] = []

    def run() -> None:
        results.append(vf.score_visual_fidelity(img, "q"))

    threads = [threading.Thread(target=run) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1
    assert all(r["status"] == vf.SCORED for r in results)


# ── Device selection (real _create_backend with fake torch/open_clip) ─────────


class _FakeTorch:
    def __init__(self, cuda_ok: bool) -> None:
        self.cuda = SimpleNamespace(is_available=lambda: cuda_ok)

    def no_grad(self):
        class _NoGrad:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return _NoGrad()


class _FakeOpenClip:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def create_model_and_transforms(self, arch: str, pretrained: str | None = None, device: str | None = None):
        self.calls.append((arch, pretrained, device))
        model: Any = SimpleNamespace()

        def _eval():
            model.evaled = True
            return model

        model.eval = _eval
        return model, SimpleNamespace(), SimpleNamespace()

    def get_tokenizer(self, arch: str) -> Any:
        return SimpleNamespace(arch=arch)


def _install_fakes(monkeypatch, cuda_ok: bool) -> _FakeOpenClip:
    fake_clip = _FakeOpenClip()
    monkeypatch.setitem(sys.modules, "torch", _FakeTorch(cuda_ok=cuda_ok))
    monkeypatch.setitem(sys.modules, "open_clip", fake_clip)
    return fake_clip


def test_backend_builder_selects_cpu(monkeypatch):
    fake_clip = _install_fakes(monkeypatch, cuda_ok=False)
    backend = vf._create_backend()
    assert backend.device == "cpu"
    assert fake_clip.calls == [("ViT-B-32", "laion2b_s34b_b79k", "cpu")]
    assert backend.model.evaled is True
    assert backend.tokenizer.arch == "ViT-B-32"


def test_backend_builder_selects_cuda(monkeypatch):
    _install_fakes(monkeypatch, cuda_ok=True)
    backend = vf._create_backend()
    assert backend.device == "cuda"
    assert backend.model.evaled is True


def test_backend_builder_device_override_wins(monkeypatch):
    _install_fakes(monkeypatch, cuda_ok=True)
    backend = vf._create_backend(device_override="cpu")
    assert backend.device == "cpu"


def test_backend_builder_missing_import_is_explicit(monkeypatch, tmp_path):
    for mod in ("torch", "open_clip"):
        monkeypatch.delitem(sys.modules, mod, raising=False)
    with pytest.raises(RuntimeError, match="torch/open_clip not installed"):
        vf._create_backend()


# ── Scoring / verdict / reproducibility ────────────────────────────────────────


def test_scored_envelope_and_reproducible(monkeypatch, tmp_path):
    monkeypatch.setattr(vf, "_create_backend", lambda: _FakeBackend(score=0.3, device="cpu"))
    monkeypatch.setenv(THRESHOLD, "0.25")
    img = _write_image(tmp_path / "a.png")
    first = vf.score_visual_fidelity(img, "query used")
    second = vf.score_visual_fidelity(img, "query used")

    assert first["status"] == vf.SCORED
    assert first["score"] == pytest.approx(0.3)
    assert first["verdict"] == vf.ACCEPT
    assert first["device"] == "cpu"
    assert first["threshold"] == 0.25
    assert first["textUsed"] == "query used"
    assert first["textPolicy"] == "p1"
    assert first["method"] == "openclip_vit_b32_p1"
    assert first["architecture"] == "ViT-B-32"
    assert first["pretrained"] == "laion2b_s34b_b79k"
    assert first["gifFrame"] is None
    assert first["reason"] is None
    assert isinstance(first["latencyMs"], int) and first["latencyMs"] >= 0
    assert _without_latency(first) == _without_latency(second)


def test_verdict_threshold_boundaries(monkeypatch, tmp_path):
    monkeypatch.setattr(vf, "_create_backend", lambda: _FakeBackend(score=0.3, device="cpu"))
    img = _write_image(tmp_path / "a.png")

    monkeypatch.setenv(THRESHOLD, "0.25")
    assert vf.score_visual_fidelity(img, "q")["verdict"] == vf.ACCEPT

    monkeypatch.setenv(THRESHOLD, "0.5")
    assert vf.score_visual_fidelity(img, "q")["verdict"] == vf.REJECT

    monkeypatch.setenv(THRESHOLD, "0.30")
    result = vf.score_visual_fidelity(img, "q")
    assert result["verdict"] == vf.ACCEPT  # ties accept (score >= threshold)


def test_text_used_is_p1_query_used(monkeypatch, tmp_path):
    fake = _FakeBackend(score=0.9, device="cpu")
    monkeypatch.setattr(vf, "_create_backend", lambda: fake)
    monkeypatch.setenv(THRESHOLD, "0.25")
    vf.score_visual_fidelity(_write_image(tmp_path / "a.png"), "volcano lava glow")
    assert fake.seen_texts == ["volcano lava glow"]


# ── GIF frame 0 ────────────────────────────────────────────────────────────────


def test_gif_uses_frame_zero_and_does_not_mutate(monkeypatch, tmp_path):
    fake = _FakeBackend(score=0.3, device="cpu")
    monkeypatch.setattr(vf, "_create_backend", lambda: fake)
    monkeypatch.setenv(THRESHOLD, "0.25")
    gif = _write_gif(tmp_path / "anim.gif", first=(255, 0, 0), second=(0, 0, 255))
    before = gif.read_bytes()

    result = vf.score_visual_fidelity(gif, "q")
    after = gif.read_bytes()

    assert result["status"] == vf.SCORED
    assert result["gifFrame"] == 0
    assert before == after
    assert fake.seen_pixels[-1] == (255, 0, 0)  # frame 0 (red), not frame 1 (blue)


# ── No ML/network/weight surface at import or source level ─────────────────────


def test_no_ml_imports_at_module_level():
    tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
    banned = {
        "torch", "open_clip", "open_clip_torch", "openclip",
        "transformers", "requests", "urllib", "socket", "http", "subprocess",
    }
    found: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] in banned:
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root in banned:
                found.append(node.module or "")
    assert not found


def test_no_network_or_weight_download_code():
    source = _MODULE_PATH.read_text(encoding="utf-8")
    for token in ("from_pretrained", "requests.", "urllib.", "socket.", "mock_socket"):
        assert token not in source, token


def test_importing_module_does_not_pull_optional_stack():
    prior = {k: v for k, v in sys.modules.items()}
    # Module was already imported at top of this test file; verify that the
    # lazy import surface was never triggered by that import.
    assert "open_clip" not in sys.modules
    assert "open_clip_torch" not in sys.modules
    assert "torch" not in sys.modules


# ── Slice 2 hardening: device move + non-finite score ─────────────────────────


class _FakeTensor:
    def __init__(self) -> None:
        self.device = "cpu"
        self.to_calls: list[str] = []

    def to(self, device: str) -> "_FakeTensor":
        self.to_calls.append(device)
        self.device = device
        return self

    def unsqueeze(self, dim: int) -> "_FakeTensor":
        return self

    def norm(self, dim=None, keepdim: bool = False) -> "_FakeTensor":
        return self

    def __truediv__(self, other) -> "_FakeTensor":
        return self

    def __matmul__(self, other) -> "_FakeTensor":
        return self

    @property
    def T(self) -> "_FakeTensor":
        return self

    def item(self) -> float:
        return 1.0


class _ScoreModel:
    def __init__(self) -> None:
        self.encode_text_tokens: _FakeTensor | None = None
        self.encode_image_tensor: _FakeTensor | None = None

    def encode_text(self, tokens: _FakeTensor) -> _FakeTensor:
        self.encode_text_tokens = tokens
        return _FakeTensor()

    def encode_image(self, tensor: _FakeTensor) -> _FakeTensor:
        self.encode_image_tensor = tensor
        return _FakeTensor()


class _NoGrad:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_score_moves_text_tokens_to_device(monkeypatch):
    model = _ScoreModel()
    backend = vf._OpenClipBackend(
        model=model,
        tokenizer=lambda texts: _FakeTensor(),
        preprocess=lambda image: _FakeTensor(),
        device="cuda",
    )
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(no_grad=_NoGrad))

    score = backend.score(object(), "query")

    assert score == 1.0
    assert model.encode_text_tokens is not None
    assert model.encode_text_tokens.to_calls == ["cuda"]


def test_non_finite_score_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(vf, "_create_backend", lambda: _FakeBackend(score=float("nan"), device="cpu"))
    monkeypatch.setenv(THRESHOLD, "0.25")
    result = vf.score_visual_fidelity(_write_image(tmp_path / "a.png"), "q")
    assert result["status"] == vf.UNAVAILABLE
    assert result["verdict"] == vf.BYPASS
    assert result["score"] is None
    assert "non-finite" in result["reason"]


def test_infinite_score_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(vf, "_create_backend", lambda: _FakeBackend(score=float("inf"), device="cpu"))
    monkeypatch.setenv(THRESHOLD, "0.25")
    result = vf.score_visual_fidelity(_write_image(tmp_path / "a.png"), "q")
    assert result["status"] == vf.UNAVAILABLE
    assert result["verdict"] == vf.BYPASS


def test_non_numeric_score_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(vf, "_create_backend", lambda: _FakeBackend(score=None, device="cpu"))
    monkeypatch.setenv(THRESHOLD, "0.25")
    result = vf.score_visual_fidelity(_write_image(tmp_path / "a.png"), "q")
    assert result["status"] == vf.UNAVAILABLE
    assert result["verdict"] == vf.BYPASS
    assert "non-finite or non-numeric" in result["reason"]


# ── Slice 2: executor integration ─────────────────────────────────────────────


from unittest.mock import patch  # noqa: E402

from shorts_creator.assets.executor import execute_visual_sourcing_plan_v2  # noqa: E402
from shorts_creator.assets.bridge import apply_visual_assets_v2_to_metadata  # noqa: E402


WIKIMEDIA_LIVE = {
    "wikimedia_commons": {
        "enabled": True, "implemented": True, "requiresApiKey": False, "live": True,
    },
}


def _candidate(title="Test query painting", description="test scene", mime="image/jpeg"):
    return {
        "provider": "wikimedia_commons",
        "title": title,
        "description": description,
        "tags": "",
        "sourceUrl": f"https://upload.wikimedia.org/wikipedia/commons/a/ab/{title}.jpg",
        "fileUrl": f"https://upload.wikimedia.org/wikipedia/commons/a/ab/{title}.jpg",
        "thumbnailUrl": "",
        "license": "Public Domain",
        "author": "Test Author",
        "width": 1200,
        "height": 800,
        "mimeType": mime,
        "queryUsed": "test query",
        "score": 0.0,
    }


def _segment():
    return {
        "segmentIndex": 1,
        "assetPreference": "painting",
        "searchQueries": [{"text": "test query", "source": "segment.searchQuery"}],
        "generationPrompts": [],
        "providerCandidates": [{
            "provider": "wikimedia_commons",
            "priority": 1,
            "queryStrategy": "search",
            "candidateStatus": "included",
            "availability": "available",
            "requiresApiKey": False,
            "supportStrength": "medium",
            "reason": "painting — medium support",
            "exclusionReason": None,
            "warnings": [],
        }],
        "excludedProviders": [],
        "routingStatus": "ROUTABLE_WITH_WARNINGS",
        "warnings": [],
        "unsupportedReasons": [],
    }


def _plan(segments):
    return {
        "schemaVersion": 1,
        "segments": segments,
        "summary": {
            "totalSegments": len(segments),
            "routable": 0,
            "routableWithWarnings": len(segments),
            "unroutable": 0,
        },
    }


def _vf_assessment(verdict="ACCEPT", score=0.9, status="SCORED"):
    return {
        "status": status,
        "method": "openclip_vit_b32_p1",
        "architecture": "ViT-B-32",
        "pretrained": "laion2b_s34b_b79k",
        "textPolicy": "p1",
        "textUsed": "test query",
        "threshold": 0.25,
        "score": score,
        "verdict": verdict,
        "device": "cpu",
        "gifFrame": None,
        "reason": None,
        "latencyMs": 1,
    }


def _write_download(resolved, absolute_path, **kwargs):
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(b"x")
    return {"ok": True, "size": 1, "mimeType": resolved.get("mimeType"), "error": None}


def test_executor_accept_persists_assessment(tmp_path):
    plan = _plan([_segment()])
    with patch(
        "shorts_creator.assets.providers.wikimedia.resolve_wikimedia_candidate_v2",
        return_value=_candidate(),
    ), patch(
        "shorts_creator.assets.providers.wikimedia.download_wikimedia_asset_v2",
        side_effect=_write_download,
    ), patch(
        "shorts_creator.assets.executor.score_visual_fidelity",
        return_value=_vf_assessment(verdict="ACCEPT", score=0.9),
    ):
        result = execute_visual_sourcing_plan_v2(
            plan, WIKIMEDIA_LIVE, dry_run=False, job_dir=str(tmp_path),
        )
    assert len(result["resolvedAssets"]) == 1
    ra = result["resolvedAssets"][0]
    assert ra["status"] == "RESOLVED"
    assert ra["visualFidelityAssessment"]["status"] == "SCORED"
    assert ra["visualFidelityAssessment"]["verdict"] == "ACCEPT"
    codes = [w["code"] for w in result["diagnostics"]["warnings"]]
    assert not any("VISUAL_FIDELITY_BYPASS" in c for c in codes)


def test_executor_reject_deletes_and_tries_next(tmp_path):
    plan = _plan([_segment()])
    candidates = iter([
        _candidate(title="Test query first", mime="image/jpeg"),
        _candidate(title="Test query second", mime="image/png"),
    ])

    def resolve(*args, **kwargs):
        return next(candidates, None)

    def score(image_path, text):
        if str(image_path).endswith(".jpg"):
            return _vf_assessment(verdict="REJECT", score=0.1)
        return _vf_assessment(verdict="ACCEPT", score=0.9)

    with patch(
        "shorts_creator.assets.providers.wikimedia.resolve_wikimedia_candidate_v2",
        side_effect=resolve,
    ), patch(
        "shorts_creator.assets.providers.wikimedia.download_wikimedia_asset_v2",
        side_effect=_write_download,
    ), patch(
        "shorts_creator.assets.executor.score_visual_fidelity",
        side_effect=score,
    ):
        result = execute_visual_sourcing_plan_v2(
            plan, WIKIMEDIA_LIVE, dry_run=False, job_dir=str(tmp_path),
        )

    assert len(result["resolvedAssets"]) == 1
    assert result["resolvedAssets"][0]["assetPath"] == "assets/seg_001.png"
    assert result["resolvedAssets"][0]["visualFidelityAssessment"]["verdict"] == "ACCEPT"
    assert not (tmp_path / "assets" / "seg_001.jpg").exists()
    assert (tmp_path / "assets" / "seg_001.png").exists()


def test_executor_all_rejected_no_results(tmp_path):
    plan = _plan([_segment()])
    candidates = iter([_candidate(title="Test query one"), _candidate(title="Test query two")])

    def resolve(*args, **kwargs):
        return next(candidates, None)

    with patch(
        "shorts_creator.assets.providers.wikimedia.resolve_wikimedia_candidate_v2",
        side_effect=resolve,
    ), patch(
        "shorts_creator.assets.providers.wikimedia.download_wikimedia_asset_v2",
        side_effect=_write_download,
    ), patch(
        "shorts_creator.assets.executor.score_visual_fidelity",
        return_value=_vf_assessment(verdict="REJECT", score=0.1),
    ):
        result = execute_visual_sourcing_plan_v2(
            plan, WIKIMEDIA_LIVE, dry_run=False, job_dir=str(tmp_path),
        )

    assert len(result["resolvedAssets"]) == 0
    assert len(result["unresolvedSegments"]) == 1
    us = result["unresolvedSegments"][0]
    assert us["status"] == "NO_RESULTS"
    rej = us.get("visualFidelityRejections") or []
    assert len(rej) == 2
    assert all(r["verdict"] == "REJECT" for r in rej)


def test_executor_disabled_bypass(tmp_path):
    plan = _plan([_segment()])
    with patch(
        "shorts_creator.assets.providers.wikimedia.resolve_wikimedia_candidate_v2",
        return_value=_candidate(),
    ), patch(
        "shorts_creator.assets.providers.wikimedia.download_wikimedia_asset_v2",
        side_effect=_write_download,
    ), patch(
        "shorts_creator.assets.executor.score_visual_fidelity",
        return_value=_vf_assessment(status="DISABLED", verdict="BYPASS", score=None),
    ):
        result = execute_visual_sourcing_plan_v2(
            plan, WIKIMEDIA_LIVE, dry_run=False, job_dir=str(tmp_path),
        )
    assert len(result["resolvedAssets"]) == 1
    ra = result["resolvedAssets"][0]
    assert ra["visualFidelityAssessment"]["status"] == "DISABLED"
    codes = [w["code"] for w in result["diagnostics"]["warnings"]]
    assert any("VISUAL_FIDELITY_BYPASS:DISABLED" in c for c in codes)


def test_executor_unavailable_bypass(tmp_path):
    plan = _plan([_segment()])
    with patch(
        "shorts_creator.assets.providers.wikimedia.resolve_wikimedia_candidate_v2",
        return_value=_candidate(),
    ), patch(
        "shorts_creator.assets.providers.wikimedia.download_wikimedia_asset_v2",
        side_effect=_write_download,
    ), patch(
        "shorts_creator.assets.executor.score_visual_fidelity",
        return_value=_vf_assessment(status="UNAVAILABLE", verdict="BYPASS", score=None),
    ):
        result = execute_visual_sourcing_plan_v2(
            plan, WIKIMEDIA_LIVE, dry_run=False, job_dir=str(tmp_path),
        )
    assert len(result["resolvedAssets"]) == 1
    ra = result["resolvedAssets"][0]
    assert ra["visualFidelityAssessment"]["status"] == "UNAVAILABLE"
    codes = [w["code"] for w in result["diagnostics"]["warnings"]]
    assert any("VISUAL_FIDELITY_BYPASS:UNAVAILABLE" in c for c in codes)


def test_executor_default_no_threshold_unchanged(tmp_path):
    # Real scorer (torch absent, no threshold) → DISABLED bypass; RESOLVED still
    # happens exactly as before, just with a persisted DISABLED assessment.
    plan = _plan([_segment()])
    with patch(
        "shorts_creator.assets.providers.wikimedia.resolve_wikimedia_candidate_v2",
        return_value=_candidate(),
    ), patch(
        "shorts_creator.assets.providers.wikimedia.download_wikimedia_asset_v2",
        side_effect=_write_download,
    ):
        result = execute_visual_sourcing_plan_v2(
            plan, WIKIMEDIA_LIVE, dry_run=False, job_dir=str(tmp_path),
        )
    assert len(result["resolvedAssets"]) == 1
    ra = result["resolvedAssets"][0]
    assert ra["status"] == "RESOLVED"
    assert ra["visualFidelityAssessment"]["status"] == "DISABLED"
    assert ra["visualFidelityAssessment"]["verdict"] == "BYPASS"


# ── Slice 2: bridge telemetry ─────────────────────────────────────────────────


def test_bridge_propagates_visual_fidelity_assessment():
    metadata = {
        "jobId": "test-job-001",
        "script": {
            "scenes": [{
                "sceneNumber": 1,
                "visualPlan": {
                    "_schemaVersion": 2,
                    "visualSequence": [{
                        "segmentIndex": 1,
                        "assetPreference": "painting",
                        "durationFraction": 1.0,
                        "transition": "cut",
                    }],
                },
            }],
        },
    }
    executor_result = {
        "resolvedAssets": [{
            "segmentIndex": 1,
            "assetPreference": "painting",
            "status": "RESOLVED",
            "provider": "wikimedia_commons",
            "assetPath": "assets/seg_001.jpg",
            "sourceUrl": "",
            "fileUrl": "",
            "license": "Public Domain",
            "author": "Test Author",
            "mimeType": "image/jpeg",
            "width": 1200,
            "height": 800,
            "searchQueryUsed": "test query",
            "generationPromptUsed": None,
            "semanticAssessment": {"verdict": "RELEVANT", "method": "deterministic_anchor_coverage_v2"},
            "visualFidelityAssessment": _vf_assessment(verdict="ACCEPT", score=0.9),
        }],
        "unresolvedSegments": [],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)
    seg = result["assets"][0]["segments"][0]
    assert seg["visualFidelityAssessment"]["verdict"] == "ACCEPT"
    assert seg["visualFidelityAssessment"]["method"] == "openclip_vit_b32_p1"


def test_bridge_propagates_visual_fidelity_rejections():
    metadata = {
        "jobId": "test-job-001",
        "script": {
            "scenes": [{
                "sceneNumber": 1,
                "visualPlan": {
                    "_schemaVersion": 2,
                    "visualSequence": [{
                        "segmentIndex": 1,
                        "assetPreference": "painting",
                        "durationFraction": 1.0,
                        "transition": "cut",
                    }],
                },
            }],
        },
    }
    rejections = [
        _vf_assessment(verdict="REJECT", score=0.1),
        _vf_assessment(verdict="REJECT", score=0.05),
    ]
    executor_result = {
        "resolvedAssets": [],
        "unresolvedSegments": [{
            "segmentIndex": 1,
            "assetPreference": "painting",
            "status": "NO_RESULTS",
            "provider": "wikimedia_commons",
            "searchQueriesTried": ["test query"],
            "reason": "no candidate passed minimum filters",
            "visualFidelityRejections": rejections,
        }],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)
    seg = result["assets"][0]["segments"][0]
    assert seg["segmentValidationStatus"] == "FAIL"
    assert seg["_visualFidelityRejections"] == rejections
    assert seg["_visualFidelityRejections"][0]["verdict"] == "REJECT"


def test_bridge_unresolved_without_rejections_empty_list():
    metadata = {
        "jobId": "test-job-001",
        "script": {
            "scenes": [{
                "sceneNumber": 1,
                "visualPlan": {
                    "_schemaVersion": 2,
                    "visualSequence": [{
                        "segmentIndex": 1,
                        "assetPreference": "painting",
                        "durationFraction": 1.0,
                        "transition": "cut",
                    }],
                },
            }],
        },
    }
    executor_result = {
        "resolvedAssets": [],
        "unresolvedSegments": [{
            "segmentIndex": 1,
            "assetPreference": "painting",
            "status": "PROVIDER_UNAVAILABLE",
            "reason": "all candidates unavailable",
        }],
    }
    result = apply_visual_assets_v2_to_metadata(metadata, executor_result)
    seg = result["assets"][0]["segments"][0]
    assert seg["_visualFidelityRejections"] == []