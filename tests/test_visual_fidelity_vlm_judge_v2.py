"""Offline tests for the visual-fidelity-vlm-judge-v2 benchmark tool.

No OpenAI SDK calls, network calls, paid API calls, or production imports are
allowed here. Verifies the judge V2 contract: three-way verdicts, strict
reasonCode-to-verdict coherence, UNCERTAIN fail-open, assetPreference loading
from the persisted contract, cost accounting, request fingerprinting, and the
absence of leaks (humanLabel / other-model scores / secrets / base64 in outputs).
"""

from __future__ import annotations

import base64
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

import visual_fidelity_vlm_judge_v2 as judge_v2  # noqa: E402
from visual_fidelity_benchmark import ACCEPT, REJECT  # noqa: E402

UNCERTAIN = judge_v2.UNCERTAIN


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


def _preflight(req_row: dict) -> dict:
    return {
        "status": "READY",
        "model": judge_v2.MODEL,
        "detail": judge_v2.DETAIL,
        "requests": [req_row],
    }


# ── Contract constants ────────────────────────────────────────────────────────


def test_reason_code_verdict_mapping_is_complete_and_consistent():
    assert set(judge_v2.REASON_CODES) == set(judge_v2.REASON_CODE_VERDICTS)
    reject_codes = [c for c, v in judge_v2.REASON_CODE_VERDICTS.items() if REJECT in v]
    accept_codes = [c for c, v in judge_v2.REASON_CODE_VERDICTS.items() if ACCEPT in v]
    assert reject_codes
    assert accept_codes
    assert judge_v2.UNCERTAIN_CODES == ("INSUFFICIENT_VISUAL_EVIDENCE",)
    assert "INSUFFICIENT_VISUAL_EVIDENCE" in judge_v2.REASON_CODE_VERDICTS
    assert set(judge_v2.REASON_CODE_VERDICTS["INSUFFICIENT_VISUAL_EVIDENCE"]) == {
        ACCEPT,
        REJECT,
        UNCERTAIN,
    }


# ── Preflight / budget ────────────────────────────────────────────────────────


def test_default_mode_requires_explicit_preflight_or_execute(monkeypatch):
    with pytest.raises(SystemExit):
        judge_v2.main([])


def test_preflight_does_not_call_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(judge_v2, "_PROJECT_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    labels = [_entry()]
    client = FakeCountClient(count=123)
    report = judge_v2._preflight_report(labels, client, tmp_path / "preflight.json")
    assert report["status"] == "READY"
    assert report["totalInputTokens"] == 123
    assert not hasattr(client.responses, "create")
    assert (tmp_path / "preflight.json").exists()


def test_budget_over_cap_blocks_all_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(judge_v2, "_PROJECT_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    preflight = {
        "status": "COST_BUDGET_EXCEEDED",
        "model": judge_v2.MODEL,
        "detail": judge_v2.DETAIL,
        "requests": [],
    }
    client = FakeResponseClient(_response('{"verdict":"ACCEPT","reasonCode":"MATCH","shortReason":"ok"}'))
    with pytest.raises(RuntimeError, match="preflight did not authorize"):
        judge_v2.execute_phase([_entry()], client, preflight, "canonical-38")
    assert client.create_calls == []


def test_budget_differs_from_slice3a():
    assert judge_v2.MAX_TOTAL_COST_USD == 0.10


def test_cost_calculation_uses_cached_input_price():
    assert judge_v2._cost(1000, 250, 128) == pytest.approx(
        (750 * 0.20 + 250 * 0.02 + 128 * 1.20) / 1_000_000
    )


# ── Request construction ──────────────────────────────────────────────────────


def test_build_request_has_three_way_contract_and_no_leaks(tmp_path, monkeypatch):
    monkeypatch.setattr(judge_v2, "_PROJECT_ROOT", tmp_path)
    raw = _write_jpeg(tmp_path / "asset.jpg")
    entry = _entry()
    request_a, frame_a, fingerprint_a, pref_a = judge_v2.build_request(entry)
    request_b, frame_b, fingerprint_b, pref_b = judge_v2.build_request(entry)
    assert request_a == request_b
    assert fingerprint_a == fingerprint_b
    assert frame_a is None and frame_b is None
    assert pref_a is None  # no contract metadata in tmp_path
    serialized = json.dumps(request_a)
    assert "CLEARLY_RELEVANT" not in serialized
    assert "pixabay" not in serialized
    assert "TOTAL_COST" not in serialized
    assert entry["queryUsed"] in serialized
    assert base64.b64encode(raw).decode() in serialized
    assert request_a["input"][0]["content"][1]["detail"] == "high"
    assert request_a["reasoning"] == {"effort": "none"}
    assert request_a["max_output_tokens"] == 128
    schema = request_a["text"]["format"]
    assert schema["strict"] is True
    assert set(schema["schema"]["properties"]) == {
        "verdict",
        "reasonCode",
        "shortReason",
    }
    assert schema["schema"]["properties"]["verdict"]["enum"] == [ACCEPT, REJECT, UNCERTAIN]


def test_gif_uses_frame_zero_without_mutating_original(tmp_path, monkeypatch):
    monkeypatch.setattr(judge_v2, "_PROJECT_ROOT", tmp_path)
    gif_path = tmp_path / "asset.gif"
    first = Image.new("RGB", (3, 3), (255, 0, 0))
    second = Image.new("RGB", (3, 3), (0, 0, 255))
    first.save(gif_path, save_all=True, append_images=[second], duration=10, loop=0)
    before = gif_path.read_bytes()
    request, frame, _fingerprint, _pref = judge_v2.build_request(_entry("asset.gif"))
    after = gif_path.read_bytes()
    assert frame == 0
    assert before == after
    image_url = request["input"][0]["content"][1]["image_url"]
    assert image_url.startswith("data:image/png;base64,")
    decoded = base64.b64decode(image_url.split(",", 1)[1])
    with Image.open(io.BytesIO(decoded)) as converted:
        assert converted.convert("RGB").getpixel((1, 1))[0] > 200


# ── assetPreference from segment contract ─────────────────────────────────────


def test_load_asset_preference_reads_segment_contract(tmp_path, monkeypatch):
    job = tmp_path / "data" / "videos" / "test-job"
    job.mkdir(parents=True)
    (job / "metadata.json").write_text(
        json.dumps(
            {
                "script": {
                    "scenes": [
                        {
                            "sceneNumber": 1,
                            "visualPlan": {
                                "visualSequence": [
                                    {
                                        "segmentIndex": 1,
                                        "assetPreference": "photograph",
                                        "searchQuery": "test subject photograph",
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(judge_v2, "_PROJECT_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    request, _frame, _fingerprint, pref = judge_v2.build_request(_entry())
    assert pref == "photograph"
    assert "Asset preference: photograph" in request["input"][0]["content"][0]["text"]


def test_load_asset_preference_missing_contract_is_none(tmp_path, monkeypatch):
    monkeypatch.setattr(judge_v2, "_PROJECT_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    _request, _frame, _fingerprint, pref = judge_v2.build_request(_entry())
    assert pref is None


def test_load_asset_preference_sequence_mismatch_returns_none(tmp_path, monkeypatch):
    job = tmp_path / "data" / "videos" / "test-job"
    job.mkdir(parents=True)
    (job / "metadata.json").write_text(
        json.dumps(
            {
                "script": {
                    "scenes": [
                        {
                            "sceneNumber": 9,
                            "visualPlan": {
                                "visualSequence": [
                                    {
                                        "segmentIndex": 1,
                                        "assetPreference": "diagram",
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(judge_v2, "_PROJECT_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    _request, _frame, _fingerprint, pref = judge_v2.build_request(_entry())
    assert pref is None


# ── Structured output parsing ─────────────────────────────────────────────────


def test_parse_judge_output_three_way_verdicts():
    assert judge_v2.parse_judge_output(
        '{"verdict":"ACCEPT","reasonCode":"MATCH","shortReason":"fine"}'
    ) == {"verdict": ACCEPT, "reasonCode": "MATCH", "shortReason": "fine"}
    assert judge_v2.parse_judge_output(
        {"verdict": "REJECT", "reasonCode": "WRONG_ENTITY", "shortReason": "x"}
    )["verdict"] == REJECT
    assert judge_v2.parse_judge_output(
        {"verdict": "UNCERTAIN", "reasonCode": "INSUFFICIENT_VISUAL_EVIDENCE", "shortReason": "x"}
    )["verdict"] == UNCERTAIN


def test_parse_judge_output_rejects_incoherent_reason_code():
    with pytest.raises(ValueError, match="reasonCode"):
        judge_v2.parse_judge_output(
            {"verdict": ACCEPT, "reasonCode": "WRONG_ENTITY", "shortReason": "x"}
        )
    with pytest.raises(ValueError, match="reasonCode"):
        judge_v2.parse_judge_output(
            {"verdict": REJECT, "reasonCode": "MATCH", "shortReason": "x"}
        )
    with pytest.raises(ValueError, match="reasonCode"):
        judge_v2.parse_judge_output(
            {"verdict": UNCERTAIN, "reasonCode": "MATCH", "shortReason": "x"}
        )


def test_parse_judge_output_rejects_malformed():
    with pytest.raises(ValueError, match="exactly"):
        judge_v2.parse_judge_output('{"verdict":"ACCEPT","reasonCode":"MATCH"}')
    with pytest.raises(ValueError, match="shortReason"):
        judge_v2.parse_judge_output(
            {"verdict": ACCEPT, "reasonCode": "MATCH", "shortReason": ""}
        )
    with pytest.raises(ValueError, match="shortReason"):
        judge_v2.parse_judge_output(
            {"verdict": ACCEPT, "reasonCode": "MATCH", "shortReason": "x" * 181}
        )
    with pytest.raises(ValueError, match="invalid verdict"):
        judge_v2.parse_judge_output(
            {"verdict": "MAYBE", "reasonCode": "MATCH", "shortReason": "x"}
        )
    with pytest.raises(ValueError, match="invalid reasonCode"):
        judge_v2.parse_judge_output(
            {"verdict": ACCEPT, "reasonCode": "NOPE", "shortReason": "x"}
        )
    with pytest.raises(ValueError, match="not valid JSON"):
        judge_v2.parse_judge_output("{not json")


# ── Operational metrics (UNCERTAIN => ACCEPT) ─────────────────────────────────


def test_operational_verdict_fail_open():
    assert judge_v2.operational_verdict(UNCERTAIN) == ACCEPT
    assert judge_v2.operational_verdict("ACCEPT") == ACCEPT
    assert judge_v2.operational_verdict("REJECT") == REJECT


def test_phase_report_counts_uncertain_as_accept(tmp_path, monkeypatch):
    monkeypatch.setattr(judge_v2, "_PROJECT_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    good = _entry(label="CLEARLY_RELEVANT")
    bad = _entry(asset_path="bad.jpg", label="FALSE_POSITIVE_OR_UNUSABLE")
    _write_jpeg(tmp_path / "bad.jpg")
    results = [
        {
            "assetPath": good["assetPath"],
            "verdict": UNCERTAIN,
            "reasonCode": "INSUFFICIENT_VISUAL_EVIDENCE",
            "latencySeconds": 1.0,
        },
        {
            "assetPath": bad["assetPath"],
            "verdict": REJECT,
            "reasonCode": "IRRELEVANT",
            "latencySeconds": 2.0,
        },
    ]
    report = judge_v2._phase_report([good, bad], results, "canonical-38")
    assert report["verdictDistribution"] == {"ACCEPT": 0, "REJECT": 1, "UNCERTAIN": 1}
    assert report["operational"]["uncertainOperationalizedAsAccept"] == 1
    metrics = report["benchmarkMetrics"]
    assert metrics["acceptableRetained"] == 1
    assert metrics["badRejected"] == 1
    assert metrics["falseAcceptances"] == 0
    assert metrics["falseRejections"] == 0


# ── Execution ─────────────────────────────────────────────────────────────────


def test_execute_records_usage_cost_and_maps_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(judge_v2, "_PROJECT_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    entry = _entry()
    request, frame, fingerprint, pref = judge_v2.build_request(entry)
    client = FakeResponseClient(
        _response(
            '{"verdict":"REJECT","reasonCode":"WRONG_ENTITY","shortReason":"x"}',
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=12,
                input_tokens_details=SimpleNamespace(cached_tokens=100),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            ),
        )
    )
    result = judge_v2.execute_phase(
        [entry], client, _preflight({"assetPath": entry["assetPath"], "requestFingerprint": fingerprint, "gifFrame": frame}), "canonical-38"
    )
    assert result["status"] == "COMPLETED"
    assert result["results"][0]["verdict"] == REJECT
    assert result["results"][0]["reasonCode"] == "WRONG_ENTITY"
    assert result["results"][0]["usage"]["cachedInputTokens"] == 100
    assert result["totalCostUsd"] > 0
    assert result["benchmarkMetrics"]["falseRejections"] == 1
    assert len(client.create_calls) == 1


def test_partial_api_failure_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(judge_v2, "_PROJECT_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    entry = _entry()
    _request, frame, fingerprint, _pref = judge_v2.build_request(entry)

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

    result = judge_v2.execute_phase(
        [entry], FailingClient(), _preflight({"assetPath": entry["assetPath"], "requestFingerprint": fingerprint, "gifFrame": frame}), "canonical-38"
    )
    assert result["status"] == "PARTIAL_FAILURE"
    assert result["results"][0]["status"] == "ERROR"
    assert result["results"][0]["errorType"] == "TimeoutError"


def test_api_key_is_not_persisted(tmp_path, monkeypatch):
    monkeypatch.setattr(judge_v2, "_PROJECT_ROOT", tmp_path)
    _write_jpeg(tmp_path / "asset.jpg")
    secret = "sk-test-never-persist-this"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    client = FakeCountClient(count=100)
    output = tmp_path / "preflight.json"
    judge_v2._preflight_report([_entry()], client, output)
    assert secret not in output.read_text(encoding="utf-8")


def test_no_production_runtime_imports():
    source = Path(_ROOT / "tools/visual_fidelity_vlm_judge_v2.py").read_text(
        encoding="utf-8"
    )
    assert "shorts_creator" not in source
    assert "from src" not in source
    assert "import src" not in source
    assert "from bin" not in source
    assert "import bin" not in source