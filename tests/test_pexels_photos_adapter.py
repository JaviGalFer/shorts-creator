"""Offline tests for Pexels shared infrastructure and Photos candidates."""

from __future__ import annotations

import inspect
import io
import json
from pathlib import Path
import socket
import sys
import urllib.error

import pytest

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

from shorts_creator.assets.providers import pexels
from shorts_creator.assets.providers.pexels import (
    AUTH_ERROR,
    CREDENTIAL_MISSING,
    MALFORMED_RESPONSE,
    NETWORK_ERROR,
    RATE_LIMITED,
    PexelsClientError,
    get_json,
)
from shorts_creator.assets.providers.pexels_photos import (
    BM25_B,
    BM25_K1,
    NO_RESULTS,
    PROVISIONAL_BM25,
    map_photo_response,
    normalized_bm25_tokens,
    order_candidates_bm25,
    search_pexels_photos,
)


class _Response:
    def __init__(self, payload, headers=None):
        self._body = json.dumps(payload).encode("utf-8") if not isinstance(payload, bytes) else payload
        self.headers = headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _photo(photo_id: int, alt: str = "castle stone") -> dict:
    return {
        "id": photo_id,
        "width": 3000,
        "height": 4000,
        "url": f"https://www.pexels.com/photo/{photo_id}/",
        "photographer": "Ada Photographer",
        "photographer_url": "https://www.pexels.com/@ada",
        "photographer_id": 99,
        "alt": alt,
        "src": {
            "original": f"https://images.pexels.com/photos/{photo_id}/original.jpg",
            "large2x": f"https://images.pexels.com/photos/{photo_id}/large2x.jpg",
        },
    }


def test_credential_resolution_prefers_process_environment(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("PEXELS_API_KEY=file-secret\n", encoding="utf-8")
    monkeypatch.setattr("shorts_creator.assets.provider_credentials.PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("PEXELS_API_KEY", "process-secret")
    assert pexels.resolve_pexels_api_key() == "process-secret"


def test_credential_resolution_reads_project_env_without_serializing_secret(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("PEXELS_API_KEY=file-secret\n", encoding="utf-8")
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.setattr("shorts_creator.assets.provider_credentials.PROJECT_ROOT", tmp_path)
    assert pexels.resolve_pexels_api_key() == "file-secret"


def test_client_sends_exact_authorization_path_params_timeout_and_sanitized_telemetry(monkeypatch):
    observed = {}

    def fake_urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["authorization"] = request.get_header("Authorization")
        observed["timeout"] = timeout
        return _Response({"photos": []}, {
            "X-Ratelimit-Remaining": "24999", "Retry-After": "2", "X-Ignored": "secret",
        })

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = get_json(
        path="/v1/videos/search", params={"query": "castle", "page": 1},
        api_key="very-secret", timeout=12,
    )
    assert observed == {
        "url": "https://api.pexels.com/v1/videos/search?query=castle&page=1",
        "authorization": "very-secret", "timeout": 12,
    }
    assert "very-secret" not in observed["url"]
    assert result.telemetry == {"x-ratelimit-remaining": "24999", "retry-after": "2"}


@pytest.mark.parametrize("status", [401, 403])
def test_client_normalizes_auth_errors_without_key_leak(monkeypatch, status):
    secret = "do-not-leak"

    def fail(*_args, **_kwargs):
        raise urllib.error.HTTPError("https://api.pexels.com/v1/search", status, "bad", {}, io.BytesIO())

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(PexelsClientError) as raised:
        get_json(path="/v1/search", params={"query": "x"}, api_key=secret)
    assert raised.value.code == AUTH_ERROR
    assert secret not in str(raised.value)


def test_client_normalizes_rate_network_and_malformed_errors(monkeypatch):
    def rate_limited(*_args, **_kwargs):
        raise urllib.error.HTTPError("https://api.pexels.com/v1/search", 429, "rate", {}, io.BytesIO())

    monkeypatch.setattr("urllib.request.urlopen", rate_limited)
    with pytest.raises(PexelsClientError, match="rate limit") as raised:
        get_json(path="/v1/search", params={}, api_key="key")
    assert raised.value.code == RATE_LIMITED

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(socket.timeout()))
    with pytest.raises(PexelsClientError) as raised:
        get_json(path="/v1/search", params={}, api_key="key")
    assert raised.value.code == NETWORK_ERROR

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: _Response(b"not json"))
    with pytest.raises(PexelsClientError) as raised:
        get_json(path="/v1/search", params={}, api_key="key")
    assert raised.value.code == MALFORMED_RESPONSE


def test_client_rejects_missing_credentials_and_absolute_paths():
    with pytest.raises(PexelsClientError) as raised:
        get_json(path="/v1/search", params={}, api_key=None)
    assert raised.value.code == CREDENTIAL_MISSING
    with pytest.raises(ValueError, match="INVALID_PEXELS_PATH"):
        get_json(path="https://example.test", params={}, api_key="key")


def test_photo_mapping_preserves_provenance_and_raw_rank():
    result = map_photo_response({"photos": [_photo(10), _photo(11)]}, "castle photograph")
    first, second = result.candidates
    assert result.status == "OK"
    assert [first.pexels_query_rank, second.pexels_query_rank] == [1, 2]
    assert first.pexels_photo_id == "10"
    assert first.envelope.provider == "pexels"
    assert first.envelope.provider_asset_id == "10"
    assert first.envelope.source_url == "https://www.pexels.com/photo/10/"
    assert first.envelope.acquisition_url.endswith("/10/original.jpg")
    assert first.envelope.preview_url.endswith("/10/large2x.jpg")
    assert first.envelope.semantic_metadata.description == "castle stone"
    assert first.envelope.attribution.author == "Ada Photographer"
    assert first.envelope.attribution.author_url == "https://www.pexels.com/@ada"
    assert first.photographer_id == "99"
    assert first.envelope.provider_rank is None


def test_photo_mapping_handles_no_results_and_invalid_payloads():
    assert map_photo_response({"photos": []}, "castle").status == NO_RESULTS
    with pytest.raises(PexelsClientError) as raised:
        map_photo_response({"photos": {}}, "castle")
    assert raised.value.code == MALFORMED_RESPONSE
    with pytest.raises(PexelsClientError) as raised:
        map_photo_response({"photos": [{"id": 1}]}, "castle")
    assert raised.value.code == MALFORMED_RESPONSE


def test_bm25_is_deterministic_fixed_and_ties_keep_raw_order():
    candidates = map_photo_response({"photos": [
        _photo(2, "castle stone wall"), _photo(1, "castle stone wall"), _photo(3, "engine piston"),
    ]}, "castle photograph").candidates
    ordered = order_candidates_bm25("castle photograph", candidates)
    assert (BM25_K1, BM25_B) == (1.2, 0.75)
    assert [item.pexels_photo_id for item in ordered] == ["2", "1", "3"]
    assert [item.envelope.provider_rank for item in ordered] == [1, 2, 3]
    assert all(item.selector_identity == PROVISIONAL_BM25 for item in ordered)
    assert all(item.selector_score == item.envelope.provider_score for item in ordered)
    assert normalized_bm25_tokens("The CAFÉ photograph") == frozenset({"caf"})


def test_search_uses_exact_photos_params_and_does_not_expose_key(monkeypatch):
    observed = {}

    def fake_get_json(**kwargs):
        observed.update(kwargs)
        return pexels.PexelsJsonResponse({"photos": [_photo(1)]}, {})

    monkeypatch.setattr("shorts_creator.assets.providers.pexels_photos.get_json", fake_get_json)
    result = search_pexels_photos("castle photograph", api_key="not-persisted", timeout=7)
    assert result.status == "OK"
    assert observed["path"] == "/v1/search"
    assert observed["params"] == {
        "query": "castle photograph", "orientation": "portrait", "locale": "en-US", "page": 1, "per_page": 15,
    }
    assert observed["timeout"] == 7
    assert "not-persisted" not in repr(result)


def test_slice_one_has_no_evaluation_or_ml_dependencies():
    import shorts_creator.assets.providers.pexels_photos as photos

    source = inspect.getsource(photos)
    for forbidden in ("tools.", "fixtures", "evaluations", "open_clip", "torch", "transformers"):
        assert forbidden not in source
