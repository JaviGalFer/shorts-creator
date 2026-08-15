"""Tests for Wikimedia provider client v2 — mock HTTP only.

Run: python3 -m pytest tests/test_visual_provider_wikimedia_v2.py -v
"""

import json
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

from shorts_creator.assets.providers.wikimedia import (
    resolve_wikimedia_candidate_v2,
    download_wikimedia_asset_v2,
    _extract_query_text,
    WikimediaRateLimitedError,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _search_response(titles):
    prefixed = [t if t.startswith("File:") else f"File:{t}" for t in titles]
    return json.dumps({
        "query": {
            "search": [{"title": t} for t in prefixed],
        },
    }).encode("utf-8")


def _imageinfo_response(title, width=1200, height=800, mime="image/jpeg",
                         license_name="Public Domain", author="Test Author",
                         file_url=None, thumb_url=None):
    if file_url is None:
        file_url = f"https://upload.wikimedia.org/wikipedia/commons/a/ab/{title}.jpg"
    thumb_url = thumb_url or f"https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/{title}.jpg/200px-{title}.jpg"
    data = {
        "query": {
            "pages": {
                "123": {
                    "title": f"File:{title}",
                    "imageinfo": [{
                        "url": file_url,
                        "thumburl": thumb_url,
                        "width": width,
                        "height": height,
                        "mime": mime,
                        "extmetadata": {
                            "LicenseShortName": {"value": license_name},
                            "Artist": {"value": author},
                            "ImageDescription": {"value": f"Description of {title}"},
                        },
                    }],
                },
            },
        },
    }
    return json.dumps(data).encode("utf-8")


def _batch_imageinfo_response(*entries):
    """Build a batched imageinfo response for multiple title entries.

    Each entry is a dict with keys: title, width, height, mime, license,
    author, description, fileUrl.
    """
    pages = {}
    for i, entry in enumerate(entries):
        pid = str(100 + i)
        title = entry.get("title", f"Image{i}.jpg")
        w = entry.get("width", 1200)
        h = entry.get("height", 800)
        mime = entry.get("mime", "image/jpeg")
        license_name = entry.get("license", "Public Domain")
        author = entry.get("author", "Test Author")
        description = entry.get("description", f"Description of {title}")
        file_url = entry.get("fileUrl", f"https://upload.wikimedia.org/wikipedia/commons/a/ab/{title}.jpg")
        thumb_url = entry.get("thumbUrl", f"https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/{title}.jpg/200px-{title}.jpg")
        page_key = f"File:{title}" if not title.startswith("File:") else title
        pages[pid] = {
            "title": page_key,
            "imageinfo": [{
                "url": file_url,
                "thumburl": thumb_url,
                "width": w,
                "height": h,
                "mime": mime,
                "extmetadata": {
                    "LicenseShortName": {"value": license_name},
                    "Artist": {"value": author},
                    "ImageDescription": {"value": description},
                },
            }],
        }
    return json.dumps({"query": {"pages": pages}}).encode("utf-8")


def _imageinfo_no_extmeta(title):
    data = {
        "query": {
            "pages": {
                "123": {
                    "title": f"File:{title}",
                    "imageinfo": [{
                        "url": f"https://upload.wikimedia.org/wikipedia/commons/a/ab/{title}.jpg",
                        "thumburl": "",
                        "width": 1200,
                        "height": 800,
                        "mime": "image/jpeg",
                        "extmetadata": {},
                    }],
                },
            },
        },
    }
    return json.dumps(data).encode("utf-8")


def _mock_urlopen_sequence(responses, content_type="image/jpeg"):
    calls = {"count": 0}

    def _side_effect(req, timeout=None):
        idx = calls["count"]
        calls["count"] += 1
        if idx >= len(responses):
            raise urllib.error.HTTPError(
                req.full_url or "", 500, "Internal Error", {}, None,
            )
        if isinstance(responses[idx], Exception):
            raise responses[idx]
        mock = MagicMock()
        mock.read.return_value = responses[idx] if isinstance(responses[idx], bytes) else responses[idx].encode("utf-8")
        mock.headers = {"Content-Type": content_type}
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    return _side_effect


# ── Query text extraction ────────────────────────────────────────────────────


class TestQueryTextExtraction:
    def test_string_query(self):
        assert _extract_query_text("hello world") == "hello world"

    def test_dict_query(self):
        assert _extract_query_text({"text": "hello world"}) == "hello world"

    def test_empty_string(self):
        assert _extract_query_text("") == ""

    def test_none(self):
        assert _extract_query_text(None) == ""

    def test_non_string(self):
        assert _extract_query_text(123) == ""

    def test_dict_no_text_key(self):
        assert _extract_query_text({"other": "value"}) == ""

    def test_truncate_long(self):
        long_q = "x" * 300
        assert len(_extract_query_text(long_q)) == 200


# ── Search / resolve ─────────────────────────────────────────────────────────


class TestResolveHappyPath:
    def test_resolve_returns_candidate_from_first_query(self):
        responses = [
            _search_response(["Test Image.jpg"]),
            _imageinfo_response("Test Image.jpg"),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is not None
            assert result["provider"] == "wikimedia_commons"
            assert result["title"] == "Description of Test Image.jpg"
            assert result["license"] == "Public Domain"
            assert result["author"] == "Test Author"
            assert result["width"] == 1200
            assert result["height"] == 800
            assert result["mimeType"] == "image/jpeg"
            assert "fileUrl" in result
            assert "sourceUrl" in result
            assert result["fileUrl"].startswith("https://upload.wikimedia.org/")
            assert result["sourceUrl"].startswith("https://commons.wikimedia.org/wiki/File:")
            assert result["sourceUrl"] != result["fileUrl"]
            assert result["queryUsed"] == "test query"
            assert result["score"] == 0.0

    def test_resolve_uses_first_query_with_results(self):
        responses = [
            _search_response([]),                              # first query empty
            _search_response(["Test Image.jpg"]),               # second query has results
            _imageinfo_response("Test Image.jpg"),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(
                ["no results", "test query"],
            )
            assert result is not None
            assert result["queryUsed"] == "test query"


class TestResolveNoResults:
    def test_empty_search_results(self):
        responses = [_search_response([])]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is None

    def test_all_queries_no_results(self):
        responses = [
            _search_response([]),
            _search_response([]),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["q1", "q2"])
            assert result is None

    def test_no_queries(self):
        result = resolve_wikimedia_candidate_v2([])
        assert result is None

    def test_empty_text_queries(self):
        result = resolve_wikimedia_candidate_v2(["", "  "])
        assert result is None


class TestResolveRejectsSVG:
    def test_svg_candidate_rejected(self):
        responses = [
            _search_response(["Test Image.svg"]),
            _imageinfo_response("Test Image.svg", mime="image/svg+xml"),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is None

    def test_svg_candidate_rejected_non_svg_accepted(self):
        responses = [
            _search_response(["SVG Image.svg", "Good Image.jpg"]),
            _batch_imageinfo_response(
                {"title": "Good Image.jpg"},
            ),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is not None
            assert "Good" in result["sourceUrl"]


class TestResolveDimensionFilters:
    def test_below_min_width_rejected(self):
        responses = [
            _search_response(["Small.jpg"]),
            _imageinfo_response("Small.jpg", width=200, height=800),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(
                ["test query"], min_width=400,
            )
            assert result is None

    def test_below_min_height_rejected(self):
        responses = [
            _search_response(["Small.jpg"]),
            _imageinfo_response("Small.jpg", width=1200, height=200),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(
                ["test query"], min_height=400,
            )
            assert result is None

    def test_missing_dimensions_rejected(self):
        responses = [
            _search_response(["NoDim.jpg"]),
            _imageinfo_response("NoDim.jpg", width=0, height=0),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is None


class TestResolveV2DimensionContract:
    """Tests using the v2 canonical contract (min_width=720, min_height=720)."""

    def test_first_candidate_700x435_rejected_second_1200x900_accepted(self):
        """First candidate is too small, second passes — selects the second."""
        responses = [
            _search_response(["Small.jpg", "Good.jpg"]),
            _batch_imageinfo_response(
                {"title": "Small.jpg", "width": 700, "height": 435},
                {"title": "Good.jpg", "width": 1200, "height": 900},
            ),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is not None
            assert "Good" in result["sourceUrl"]

    def test_first_query_all_small_second_query_has_valid(self):
        """First query only returns small candidates, second query succeeds."""
        responses = [
            _search_response(["Tiny1.jpg"]),
            _imageinfo_response("Tiny1.jpg", width=700, height=435),
            _search_response(["Good.jpg"]),
            _imageinfo_response("Good.jpg", width=1200, height=900),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["small query", "good query"])
            assert result is not None
            assert result["queryUsed"] == "good query"
            assert "Good" in result["sourceUrl"]

    def test_all_candidates_small_returns_none(self):
        """All candidates below 720 in at least one dimension → None."""
        responses = [
            _search_response(["Small1.jpg", "Small2.jpg"]),
            _batch_imageinfo_response(
                {"title": "Small1.jpg", "width": 700, "height": 800},
                {"title": "Small2.jpg", "width": 1200, "height": 600},
            ),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is None

    def test_720x720_accepted(self):
        """Exact minimum dimensions are accepted."""
        responses = [
            _search_response(["Exact.jpg"]),
            _imageinfo_response("Exact.jpg", width=720, height=720),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is not None

    def test_719x1000_rejected(self):
        """719 width is below 720 even with tall height — rejected."""
        responses = [
            _search_response(["Narrow.jpg"]),
            _imageinfo_response("Narrow.jpg", width=719, height=1000),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is None

    def test_svg_still_rejected(self):
        """SVG files are still rejected at the title level."""
        responses = [
            _search_response(["Vector.svg"]),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is None


class TestCanonicalConstantsImported:
    """Verify Wikimedia provider uses canonical constants from renderability module."""

    def test_default_width_matches_canonical(self):
        from shorts_creator.assets.renderability import MIN_V2_ASSET_WIDTH
        from shorts_creator.assets.providers.wikimedia import resolve_wikimedia_candidate_v2 as resolve_fn
        import inspect
        sig = inspect.signature(resolve_fn)
        assert sig.parameters["min_width"].default == MIN_V2_ASSET_WIDTH

    def test_default_height_matches_canonical(self):
        from shorts_creator.assets.renderability import MIN_V2_ASSET_HEIGHT
        from shorts_creator.assets.providers.wikimedia import resolve_wikimedia_candidate_v2 as resolve_fn
        import inspect
        sig = inspect.signature(resolve_fn)
        assert sig.parameters["min_height"].default == MIN_V2_ASSET_HEIGHT

    def test_explicit_min_width_still_overridable(self):
        """Explicit min_width should still work without changing the constant."""
        responses = [
            _search_response(["Small.jpg"]),
            _imageinfo_response("Small.jpg", width=200, height=800),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(
                ["test query"], min_width=400,
            )
            assert result is None

    def test_explicit_min_height_still_overridable(self):
        """Explicit min_height should still work without changing the constant."""
        responses = [
            _search_response(["Small.jpg"]),
            _imageinfo_response("Small.jpg", width=1200, height=200),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(
                ["test query"], min_height=400,
            )
            assert result is None


class TestResolveMissingFileUrl:
    def test_missing_file_url_rejected(self):
        responses = [
            _search_response(["Missing.jpg"]),
            _imageinfo_response("Missing.jpg", file_url=""),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is None


class TestResolveMetadataFallbacks:
    def test_no_extmetadata_defaults(self):
        responses = [
            _search_response(["Test.jpg"]),
            _imageinfo_no_extmeta("Test.jpg"),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is not None
            assert result["license"] == "unknown"
            assert result["author"] == "Unknown"
            assert "File:Test" in result["title"]


class TestResolveErrorHandling:
    def test_json_decode_error(self):
        responses = [b"not json"]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is None

    def test_http_error_500(self):
        def _raise_500(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url or "", 500, "Internal Server Error", {}, None,
            )
        with patch("urllib.request.urlopen", side_effect=_raise_500):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is None

    def test_urlerror(self):
        def _raise_url(req, timeout=None):
            raise urllib.error.URLError("connection refused")
        with patch("urllib.request.urlopen", side_effect=_raise_url):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is None

    def test_socket_timeout(self):
        def _raise_timeout(req, timeout=None):
            raise socket.timeout("timed out")
        with patch("urllib.request.urlopen", side_effect=_raise_timeout):
            result = resolve_wikimedia_candidate_v2(["test query"])
            assert result is None


class TestUserAgentHeader:
    def test_default_user_agent_set(self):
        responses = [
            _search_response(["Test.jpg"]),
            _imageinfo_response("Test.jpg"),
        ]
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock = MagicMock()
            mock.read.return_value = responses[0]
            mock.headers = {"Content-Type": "application/json"}

            mock2 = MagicMock()
            mock2.read.return_value = responses[1]
            mock2.headers = {"Content-Type": "application/json"}

            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock(return_value=False)
            mock2.__enter__ = MagicMock(return_value=mock2)
            mock2.__exit__ = MagicMock(return_value=False)

            mock_urlopen.side_effect = [mock, mock2]

            resolve_wikimedia_candidate_v2(["test query"])

            calls = mock_urlopen.call_args_list
            for call in calls:
                req = call[0][0]
                ua = req.headers.get("User-agent", "")
                assert "shorts-creator" in ua

    def test_custom_user_agent(self):
        custom_ua = "my-bot/2.0"
        responses = [
            _search_response(["Test.jpg"]),
            _imageinfo_response("Test.jpg"),
        ]
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock = MagicMock()
            mock.read.return_value = responses[0]
            mock.headers = {"Content-Type": "application/json"}

            mock2 = MagicMock()
            mock2.read.return_value = responses[1]
            mock2.headers = {"Content-Type": "application/json"}

            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock(return_value=False)
            mock2.__enter__ = MagicMock(return_value=mock2)
            mock2.__exit__ = MagicMock(return_value=False)

            mock_urlopen.side_effect = [mock, mock2]

            resolve_wikimedia_candidate_v2(["test query"], user_agent=custom_ua)

            calls = mock_urlopen.call_args_list
            for call in calls:
                req = call[0][0]
                assert req.headers.get("User-agent") == custom_ua


# ── Download ─────────────────────────────────────────────────────────────────


class TestDownloadHappyPath:
    def test_download_writes_file(self, tmp_path):
        dest = tmp_path / "test.jpg"
        candidate = {"fileUrl": "https://example.com/image.jpg"}
        image_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 2000

        mock_resp = MagicMock()
        mock_resp.read.return_value = image_bytes
        mock_resp.headers = {"Content-Type": "image/jpeg"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = download_wikimedia_asset_v2(candidate, dest)

        assert result["ok"] is True
        assert result["path"] == str(dest)
        assert result["size"] == len(image_bytes)
        assert result["mimeType"] == "image/jpeg"
        assert result["error"] is None
        assert dest.exists()
        assert dest.read_bytes() == image_bytes

    def test_download_creates_parent_dirs(self, tmp_path):
        dest = tmp_path / "sub" / "deep" / "test.jpg"
        candidate = {"fileUrl": "https://example.com/image.jpg"}
        image_bytes = b"a" * 1500

        mock_resp = MagicMock()
        mock_resp.read.return_value = image_bytes
        mock_resp.headers = {"Content-Type": "image/jpeg"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = download_wikimedia_asset_v2(candidate, dest)

        assert result["ok"] is True
        assert dest.exists()


class TestDownloadRejects:
    def test_rejects_non_image_content_type(self, tmp_path):
        dest = tmp_path / "test.jpg"
        candidate = {"fileUrl": "https://example.com/data.json"}

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not an image" * 100
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = download_wikimedia_asset_v2(candidate, dest)

        assert result["ok"] is False
        assert "invalid Content-Type" in result["error"]
        assert not dest.exists()

    def test_rejects_svg_content_type(self, tmp_path):
        dest = tmp_path / "test.svg"
        candidate = {"fileUrl": "https://example.com/image.svg"}

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<svg>" * 100
        mock_resp.headers = {"Content-Type": "image/svg+xml"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = download_wikimedia_asset_v2(candidate, dest)

        assert result["ok"] is False
        assert not dest.exists()

    def test_rejects_too_small_file(self, tmp_path):
        dest = tmp_path / "tiny.jpg"
        candidate = {"fileUrl": "https://example.com/tiny.jpg"}

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"x" * 50
        mock_resp.headers = {"Content-Type": "image/jpeg"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = download_wikimedia_asset_v2(candidate, dest)

        assert result["ok"] is False
        assert "too small" in result["error"].lower()
        assert not dest.exists()

    def test_refuses_overwrite(self, tmp_path):
        dest = tmp_path / "exists.jpg"
        dest.write_bytes(b"existing")
        candidate = {"fileUrl": "https://example.com/image.jpg"}

        result = download_wikimedia_asset_v2(candidate, dest)

        assert result["ok"] is False
        assert "already exists" in result["error"]

    def test_rejects_no_file_url(self, tmp_path):
        dest = tmp_path / "test.jpg"
        candidate = {"fileUrl": ""}

        result = download_wikimedia_asset_v2(candidate, dest)

        assert result["ok"] is False
        assert "no fileUrl" in result["error"]


class TestDownloadErrors:
    def test_http_error_during_download(self, tmp_path):
        dest = tmp_path / "test.jpg"
        candidate = {"fileUrl": "https://example.com/image.jpg"}

        def _raise_404(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url or "", 404, "Not Found", {}, None,
            )

        with patch("urllib.request.urlopen", side_effect=_raise_404):
            result = download_wikimedia_asset_v2(candidate, dest)

        assert result["ok"] is False
        assert result["error"] == "download failed"


# ── HTTP 429 retry tests ─────────────────────────────────────────────────────


class TestHttp429Retry:
    def test_429_retries_and_succeeds(self):
        search_bytes = _search_response(["Test.jpg"])
        info_bytes = _imageinfo_response("Test.jpg")
        error_raised = {"count": 0}

        def _side_effect(req, timeout=None):
            if error_raised["count"] == 0:
                error_raised["count"] = 1
                raise urllib.error.HTTPError(
                    req.full_url or "", 429, "Too Many Requests", {}, None,
                )
            url = req.full_url or ""
            data = info_bytes if "imageinfo" in url else search_bytes
            mock = MagicMock()
            mock.read.return_value = data
            mock.headers = {"Content-Type": "application/json"}
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock()
            return mock

        with patch("urllib.request.urlopen", side_effect=_side_effect):
            with patch("time.sleep") as mock_sleep:
                result = resolve_wikimedia_candidate_v2(["test query"])

        assert result is not None
        assert result["title"] == "Description of Test.jpg"
        mock_sleep.assert_called_once()

    def test_429_calls_sleep_once_with_default_duration(self):
        search_bytes = _search_response(["Test.jpg"])
        info_bytes = _imageinfo_response("Test.jpg")
        error_raised = {"count": 0}

        def _side_effect(req, timeout=None):
            if error_raised["count"] == 0:
                error_raised["count"] = 1
                raise urllib.error.HTTPError(
                    req.full_url or "", 429, "Too Many Requests", {}, None,
                )
            url = req.full_url or ""
            data = info_bytes if "imageinfo" in url else search_bytes
            mock = MagicMock()
            mock.read.return_value = data
            mock.headers = {"Content-Type": "application/json"}
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock()
            return mock

        with patch("urllib.request.urlopen", side_effect=_side_effect):
            with patch("time.sleep") as mock_sleep:
                resolve_wikimedia_candidate_v2(["test query"])

        mock_sleep.assert_called_once()
        args, _ = mock_sleep.call_args
        assert args[0] == 1.0

    def test_non_429_http_error_does_not_retry(self):
        def _raise_500(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url or "", 500, "Internal Error", {}, None,
            )

        with patch("urllib.request.urlopen", side_effect=_raise_500):
            with patch("time.sleep") as mock_sleep:
                result = resolve_wikimedia_candidate_v2(["test query"])

        assert result is None
        mock_sleep.assert_not_called()

    def test_429_retry_also_fails_raises_rate_limited(self):
        def _always_429(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url or "", 429, "Too Many Requests", {}, None,
            )

        with patch("urllib.request.urlopen", side_effect=_always_429):
            with patch("time.sleep"):
                with pytest.raises(WikimediaRateLimitedError):
                    resolve_wikimedia_candidate_v2(["test query"])

    def test_user_agent_preserved_on_retry(self):
        search_bytes = _search_response(["Test.jpg"])
        info_bytes = _imageinfo_response("Test.jpg")
        error_raised = {"count": 0}
        captured_headers = []

        def _side_effect(req, timeout=None):
            captured_headers.append(req.headers)
            if error_raised["count"] == 0:
                error_raised["count"] = 1
                raise urllib.error.HTTPError(
                    req.full_url or "", 429, "Too Many Requests", {}, None,
                )
            url = req.full_url or ""
            data = info_bytes if "imageinfo" in url else search_bytes
            mock = MagicMock()
            mock.read.return_value = data
            mock.headers = {"Content-Type": "application/json"}
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock()
            return mock

        with patch("urllib.request.urlopen", side_effect=_side_effect):
            with patch("time.sleep"):
                resolve_wikimedia_candidate_v2(
                    ["test query"], user_agent="custom-agent/2.0",
                )

        for h in captured_headers:
            assert h.get("User-agent") == "custom-agent/2.0"


# ── sourceUrl / fileUrl separation tests ─────────────────────────────────────


class TestSourceUrlFileUrlSeparation:
    def test_source_url_is_commons_page_not_file_url(self):
        responses = [
            _search_response(["Test Image.jpg"]),
            _imageinfo_response("Test Image.jpg"),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])

        assert result is not None
        assert result["sourceUrl"].startswith(
            "https://commons.wikimedia.org/wiki/File:"
        )
        assert result["fileUrl"].startswith("https://upload.wikimedia.org/")
        assert result["sourceUrl"] != result["fileUrl"]

    def test_source_url_handles_spaces_in_title(self):
        responses = [
            _search_response(["File with spaces.jpg"]),
            _imageinfo_response("File with spaces.jpg"),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])

        assert result is not None
        assert "wiki/File:File" in result["sourceUrl"]
        assert "%20with%20spaces" in result["sourceUrl"]

    def test_source_url_empty_when_title_missing(self):
        responses: list = [
            _search_response([""]),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])

        assert result is None

    def test_file_url_remains_direct_download(self):
        responses = [
            _search_response(["Test Image.jpg"]),
            _imageinfo_response("Test Image.jpg"),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])

        assert result is not None
        assert "upload.wikimedia.org" in result["fileUrl"]


# ── Candidate pool / exclusion tests ──────────────────────────────────────────

# Shared cache for pool tests
_cache: dict[str, list] = {}


class TestCandidatePoolExclusion:
    def test_two_segments_same_query_get_different_urls(self):
        import time as _time
        image1_title = "Image1.jpg"
        image2_title = "Image2.jpg"
        responses = [
            _search_response([image1_title, image2_title]),
            _batch_imageinfo_response(
                {"title": image1_title},
                {"title": image2_title},
            ),
        ]
        excluded_src: set[str] = set()
        excluded_file: set[str] = set()
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            with patch("time.sleep"):
                result1 = resolve_wikimedia_candidate_v2(
                    ["test query"],
                    excluded_source_urls=excluded_src,
                    excluded_file_urls=excluded_file,
                    cache=_cache,
                )
            assert result1 is not None
            excluded_src.add(result1["sourceUrl"])
            excluded_file.add(result1["fileUrl"])

        # Second call with same query, existing cache, exclusions
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = AssertionError("should not call HTTP again")
            result2 = resolve_wikimedia_candidate_v2(
                ["test query"],
                excluded_source_urls=excluded_src,
                excluded_file_urls=excluded_file,
                cache=_cache,
            )
            mock_urlopen.assert_not_called()
        assert result2 is not None
        assert result2["sourceUrl"] != result1["sourceUrl"]
        assert result2["fileUrl"] != result1["fileUrl"]

    def test_excluded_source_url_skipped_uses_next(self):
        responses = [
            _search_response(["Image1.jpg", "Image2.jpg"]),
            _batch_imageinfo_response(
                {"title": "Image1.jpg"},
                {"title": "Image2.jpg"},
            ),
        ]
        excluded_src = {"https://commons.wikimedia.org/wiki/File:Image1.jpg"}
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(
                ["test query"],
                excluded_source_urls=excluded_src,
            )
        assert result is not None
        assert "Image2" in result["sourceUrl"]

    def test_excluded_file_url_skipped_uses_next(self):
        responses = [
            _search_response(["Image1.jpg", "Image2.jpg"]),
            _batch_imageinfo_response(
                {"title": "Image1.jpg", "fileUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Img1.jpg"},
                {"title": "Image2.jpg", "fileUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Img2.jpg"},
            ),
        ]
        excluded_file = {"https://upload.wikimedia.org/wikipedia/commons/a/ab/Img1.jpg"}
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(
                ["test query"],
                excluded_file_urls=excluded_file,
            )
        assert result is not None
        assert "File:Image2" in result["sourceUrl"]

    def test_all_first_query_candidates_excluded_continues_second_query(self):
        excluded_src: set[str] = set()
        excluded_file: set[str] = set()
        cache: dict[str, list] = {}

        responses_q1 = [
            _search_response(["Q1A.jpg", "Q1B.jpg"]),
            _batch_imageinfo_response(
                {"title": "Q1A.jpg"},
                {"title": "Q1B.jpg"},
            ),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses_q1)):
            with patch("time.sleep"):
                r1 = resolve_wikimedia_candidate_v2(
                    ["q1", "q2"],
                    excluded_source_urls=excluded_src,
                    excluded_file_urls=excluded_file,
                    cache=cache,
                )
        assert r1 is not None
        excluded_src.add(r1["sourceUrl"])
        excluded_file.add(r1["fileUrl"])

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = AssertionError("should not call HTTP again")
            r2 = resolve_wikimedia_candidate_v2(
                ["q1", "q2"],
                excluded_source_urls=excluded_src,
                excluded_file_urls=excluded_file,
                cache=cache,
            )
            mock_urlopen.assert_not_called()
        assert r2 is not None
        assert r2["sourceUrl"] != r1["sourceUrl"]

        excluded_src.add(r2["sourceUrl"])
        excluded_file.add(r2["fileUrl"])
        responses_q2 = [
            _search_response(["Q2A.jpg"]),
            _imageinfo_response("Q2A.jpg"),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses_q2)):
            with patch("time.sleep"):
                r3 = resolve_wikimedia_candidate_v2(
                    ["q1", "q2"],
                    excluded_source_urls=excluded_src,
                    excluded_file_urls=excluded_file,
                    cache=cache,
                )
        assert r3 is not None
        assert "File:Q2A" in r3["sourceUrl"]


# ── Query cache tests ─────────────────────────────────────────────────────────


class TestQueryCache:
    def test_same_query_no_http_repeat_with_cache(self):
        image1 = _imageinfo_response("Image1.jpg")
        responses = [
            _search_response(["Image1.jpg"]),
            image1,
        ]
        cache: dict[str, list] = {}
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result1 = resolve_wikimedia_candidate_v2(["test query"], cache=cache)
        assert result1 is not None

        excluded_src = {result1["sourceUrl"]}
        excluded_file = {result1["fileUrl"]}

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = AssertionError("should not call HTTP")
            result2 = resolve_wikimedia_candidate_v2(
                ["test query"],
                cache=cache,
                excluded_source_urls=excluded_src,
                excluded_file_urls=excluded_file,
            )
            mock_urlopen.assert_not_called()
        assert result2 is None


# ── 429 rate-limited diagnosis tests ──────────────────────────────────────────


class TestRateLimitedDiagnosis:
    def test_429_exhausted_raises_rate_limited_error(self):
        from shorts_creator.assets.providers.wikimedia import WikimediaRateLimitedError

        def _always_429(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url or "", 429, "Too Many Requests", {}, None,
            )

        with patch("urllib.request.urlopen", side_effect=_always_429):
            with patch("time.sleep"):
                with pytest.raises(WikimediaRateLimitedError, match="429"):
                    resolve_wikimedia_candidate_v2(["test query"])

    def test_429_with_retry_after_header(self):
        from shorts_creator.assets.providers.wikimedia import WikimediaRateLimitedError

        error_count = [0]

        def _side_effect(req, timeout=None):
            error_count[0] += 1
            headers = {"Retry-After": "2"}
            raise urllib.error.HTTPError(
                req.full_url or "", 429, "Too Many Requests",
                headers, None,
            )

        with patch("urllib.request.urlopen", side_effect=_side_effect):
            with patch("time.sleep") as mock_sleep:
                with pytest.raises(WikimediaRateLimitedError):
                    resolve_wikimedia_candidate_v2(["test query"])

        assert error_count[0] == 2
        assert mock_sleep.call_count == 1
        args, _ = mock_sleep.call_args
        assert args[0] == 2.0

    def test_429_retry_once_without_header_defaults_1s(self):
        from shorts_creator.assets.providers.wikimedia import WikimediaRateLimitedError

        error_count = [0]

        def _side_effect(req, timeout=None):
            error_count[0] += 1
            raise urllib.error.HTTPError(
                req.full_url or "", 429, "Too Many Requests",
                {}, None,
            )

        with patch("urllib.request.urlopen", side_effect=_side_effect):
            with patch("time.sleep") as mock_sleep:
                with pytest.raises(WikimediaRateLimitedError):
                    resolve_wikimedia_candidate_v2(["test query"])

        assert error_count[0] == 2
        mock_sleep.assert_called_once()
        args, _ = mock_sleep.call_args
        assert args[0] == 1.0

    def test_valid_response_no_suitable_candidates_returns_none(self):
        """NO_RESULTS: API responded but no candidate passed."""
        responses = [
            _search_response(["Tiny.jpg"]),
            _imageinfo_response("Tiny.jpg", width=10, height=10),
        ]
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_sequence(responses)):
            result = resolve_wikimedia_candidate_v2(["test query"])
        assert result is None
