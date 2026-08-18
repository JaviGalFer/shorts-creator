"""Offline tests for the Slice 3A OpenAI benchmark tool.

No OpenAI SDK calls, network calls, paid API calls, or production imports are
allowed here.
"""

from __future__ import annotations

import base64
import copy
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = str(_ROOT / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

import visual_fidelity_api_benchmark as api_benchmark  # noqa: E402
from visual_fidelity_benchmark import ACCEPT, REJECT  # noqa: E402


def _entry(asset_path: str = "asset.jpg", label: str = "CLEARLY_RELEVANT") -> dict:
    return {
        "topic": "test topic",
        "jobId": "test-job",
        "sceneNumber": 1,
        "segmentIndex": 1,
        "assetPath": asset_path,
        "queryUsed": "test subject photograph",
        "provider": "pixabay",
        "humanLabel": label,
    }


def _write_jpeg(path: Path, color: tuple[int, int, int] = (10, 20, 30)) -> bytes:
    image = Image.new("RGB", (4, 3), color)
    image.save(path, format="JPEG")
    return path.read_bytes()


class FakeCountClient:
    def __init__(self, count: int = 100):
        self.count = count
        self.count_calls: list[dict] = []

        class InputTokens:
            def __init__(inner, outer):
                inner.outer = outer

            def count(inner, **kwargs):
                inner.outer.count_calls.append(kwargs)
                return SimpleNamespace(input_tokens=inner.outer.count)

        self.responses = SimpleNamespace(input_tokens=InputTokens(self))


class FakeResponseClient:
    def __init__(self, response):
        self.response = response
        self.create_calls: list[dict] = []

        class Responses:
            def __init__(inner, outer):
                inner.outer = outer

            def create(inner, **kwargs):
                inner.outer.create_calls.append(kwargs)
                return inner.outer.response

        self.responses = Responses(self)


def _response(raw: str, *, usage=None, status="completed"):
    return SimpleNamespace(
        status=status,
        output_text=raw,
        usage=usage
        or SimpleNamespace(
            input_tokens=100,
            output_tokens=10,
            input_tokens_details=SimpleNamespace(cached_tokens=0),
            output_tokens_details=SimpleNamespace(reasoning_tokens=0),
        ),
    )


def test_default_mode_requires_explicit_preflight_or_execute(monkeypatch):
    with pytest.raises(SystemExit):
        api_benchmark.main([])


def test_preflight_does_not_call_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(api_benchmark, "_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    labels = [_entry()]
    client = FakeCountClient(count=123)
    report = api_benchmark._preflight_report(labels, client, tmp_path / "preflight.json")
    assert report["status"] == "READY"
    assert report["totalInputTokens"] == 123
    assert not hasattr(client.responses, "create")
    assert (tmp_path / "preflight.json").exists()


def test_budget_over_cap_blocks_all_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(api_benchmark, "_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    labels = [_entry()]
    preflight = {
        "status": "COST_BUDGET_EXCEEDED",
        "model": api_benchmark.MODEL,
        "detail": api_benchmark.DETAIL,
        "requests": [],
    }
    client = FakeResponseClient(_response('{"verdict":"ACCEPT","reasonCode":"MATCH"}'))
    with pytest.raises(RuntimeError, match="preflight did not authorize"):
        api_benchmark.execute(labels, client, preflight)
    assert client.create_calls == []


def test_cost_calculation_uses_cached_input_price():
    assert api_benchmark._cost(1000, 250, 128) == pytest.approx(
        (750 * 0.20 + 250 * 0.02 + 128 * 1.20) / 1_000_000
    )


def test_build_request_is_deterministic_and_has_no_label_or_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(api_benchmark, "_ROOT", tmp_path)
    raw = _write_jpeg(tmp_path / "asset.jpg")
    entry = _entry()
    request_a, frame_a, fingerprint_a = api_benchmark.build_request(entry)
    request_b, frame_b, fingerprint_b = api_benchmark.build_request(entry)
    assert request_a == request_b
    assert fingerprint_a == fingerprint_b
    assert frame_a is None and frame_b is None
    serialized = json.dumps(request_a)
    assert "CLEARLY_RELEVANT" not in serialized
    assert "pixabay" not in serialized
    assert entry["queryUsed"] in serialized
    assert base64.b64encode(raw).decode() in serialized
    assert request_a["input"][0]["content"][1]["detail"] == "high"
    assert request_a["reasoning"] == {"effort": "none"}
    assert request_a["max_output_tokens"] == 128


def test_gif_uses_frame_zero_without_mutating_original(tmp_path, monkeypatch):
    monkeypatch.setattr(api_benchmark, "_ROOT", tmp_path)
    gif_path = tmp_path / "asset.gif"
    first = Image.new("RGB", (3, 3), (255, 0, 0))
    second = Image.new("RGB", (3, 3), (0, 0, 255))
    first.save(gif_path, save_all=True, append_images=[second], duration=10, loop=0)
    before = gif_path.read_bytes()
    request, frame, _ = api_benchmark.build_request(_entry("asset.gif"))
    after = gif_path.read_bytes()
    assert frame == 0
    assert before == after
    image_url = request["input"][0]["content"][1]["image_url"]
    assert image_url.startswith("data:image/png;base64,")
    decoded = base64.b64decode(image_url.split(",", 1)[1])
    with Image.open(io.BytesIO(decoded)) as converted:
        assert converted.convert("RGB").getpixel((1, 1))[0] > 200


def test_structured_output_parser_accept_reject_and_malformed():
    assert api_benchmark.parse_judge_output(
        '{"verdict":"ACCEPT","reasonCode":"MATCH"}'
    ) == {"verdict": ACCEPT, "reasonCode": "MATCH"}
    assert api_benchmark.parse_judge_output(
        {"verdict": "REJECT", "reasonCode": "WRONG_ENTITY"}
    )["verdict"] == REJECT
    with pytest.raises(ValueError):
        api_benchmark.parse_judge_output('{"verdict":"ACCEPT"}')
    with pytest.raises(ValueError):
        api_benchmark.parse_judge_output(
            '{"verdict":"MAYBE","reasonCode":"MATCH"}'
        )
    with pytest.raises(ValueError):
        api_benchmark.parse_judge_output(
            '{"verdict":"ACCEPT","reasonCode":"MATCH","reason":"free text"}'
        )


def test_api_key_is_not_persisted(tmp_path, monkeypatch):
    monkeypatch.setattr(api_benchmark, "_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    secret = "sk-test-never-persist-this"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    client = FakeCountClient(count=100)
    output = tmp_path / "preflight.json"
    api_benchmark._preflight_report([_entry()], client, output)
    assert secret not in output.read_text(encoding="utf-8")


def test_execute_records_usage_cost_and_maps_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(api_benchmark, "_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    entry = _entry()
    request, frame, fingerprint = api_benchmark.build_request(entry)
    preflight = {
        "status": "READY",
        "model": api_benchmark.MODEL,
        "detail": api_benchmark.DETAIL,
        "requests": [
            {
                "assetPath": entry["assetPath"],
                "requestFingerprint": fingerprint,
                "gifFrame": frame,
            }
        ],
    }
    client = FakeResponseClient(
        _response(
            '{"verdict":"REJECT","reasonCode":"WRONG_ENTITY"}',
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=12,
                input_tokens_details=SimpleNamespace(cached_tokens=100),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            ),
        )
    )
    result = api_benchmark.execute([entry], client, preflight)
    assert result["status"] == "COMPLETED"
    assert result["results"][0]["verdict"] == REJECT
    assert result["results"][0]["reasonCode"] == "WRONG_ENTITY"
    assert result["results"][0]["usage"]["cachedInputTokens"] == 100
    assert result["totalCostUsd"] > 0
    assert len(client.create_calls) == 1


def test_partial_api_failure_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(api_benchmark, "_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    entry = _entry()
    _, frame, fingerprint = api_benchmark.build_request(entry)
    preflight = {
        "status": "READY",
        "model": api_benchmark.MODEL,
        "detail": api_benchmark.DETAIL,
        "requests": [{"assetPath": entry["assetPath"], "requestFingerprint": fingerprint, "gifFrame": frame}],
    }

    class FailingClient(FakeResponseClient):
        def __init__(self):
            self.create_calls = []

            class Responses:
                def __init__(inner, outer):
                    inner.outer = outer

                def create(inner, **kwargs):
                    inner.outer.create_calls.append(kwargs)
                    raise TimeoutError("mock timeout")

            self.responses = Responses(self)

    result = api_benchmark.execute([entry], FailingClient(), preflight)
    assert result["status"] == "PARTIAL_FAILURE"
    assert result["results"][0]["status"] == "ERROR"
    assert result["results"][0]["errorType"] == "TimeoutError"


def test_no_production_runtime_imports():
    source = Path(_ROOT / "tools/visual_fidelity_api_benchmark.py").read_text(
        encoding="utf-8"
    )
    assert "shorts_creator" not in source
    assert "from src" not in source
    assert "import src" not in source
    assert "from bin" not in source
    assert "import bin" not in source
