"""Tests for Pixabay provider v2.

Run: python3 -m pytest tests/test_visual_provider_pixabay_v2.py -v

No live HTTP.  Heavy use of urllib mocking.
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

from shorts_creator.assets.providers.pixabay import (
    resolve_pixabay_candidates_v2,
    download_pixabay_asset_v2,
    _read_cache,
    _write_cache,
    _build_cache_key,
    _calculate_expected_dimensions,
    _read_jpeg_dimensions,
    _read_png_dimensions,
    _read_gif_dimensions,
    _read_webp_dimensions,
    _read_image_dimensions,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _mock_pixabay_json(hits=None, total=None):
    return json.dumps({
        "total": total if total is not None else len(hits or []),
        "totalHits": len(hits or []),
        "hits": hits or [],
    }).encode("utf-8")


def _mock_hit(
    idx=1,
    pageURL=None,
    largeImageURL=None,
    imageWidth=1920,
    imageHeight=1080,
    user="TestUser",
    tags="test, mock",
    previewURL=None,
    image_type="photo",
):
    return {
        "id": idx,
        "pageURL": pageURL or f"https://pixabay.com/photos/test-{idx}/",
        "type": image_type,
        "tags": tags,
        "previewURL": previewURL or f"https://cdn.pixabay.com/photo/preview/test-{idx}.jpg",
        "previewWidth": 150,
        "previewHeight": 84,
        "webformatURL": f"https://pixabay.com/get/test-{idx}_640.jpg",
        "webformatWidth": 640,
        "webformatHeight": 360,
        "largeImageURL": largeImageURL or f"https://pixabay.com/get/test-{idx}_1280.jpg",
        "imageWidth": imageWidth,
        "imageHeight": imageHeight,
        "imageSize": 256000,
        "views": 1000,
        "downloads": 50,
        "likes": 10,
        "comments": 2,
        "user_id": 999,
        "user": user,
        "userImageURL": "https://cdn.pixabay.com/user/test.jpg",
    }


def _mock_http_response_maker(hits=None, status=200):
    class MockResponse:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def read(self):
            return _mock_pixabay_json(hits)
    MockResponse.status = status
    return MockResponse


# ── Cache helpers ────────────────────────────────────────────────────────────


class TestCache:
    def test_build_cache_key_deterministic(self):
        k1 = _build_cache_key("cats", "en", "photo", 720, 720, 1, 20)
        k2 = _build_cache_key("cats", "en", "photo", 720, 720, 1, 20)
        assert k1 == k2

    def test_build_cache_key_different_query(self):
        k1 = _build_cache_key("cats", "en", "photo", 720, 720, 1, 20)
        k2 = _build_cache_key("dogs", "en", "photo", 720, 720, 1, 20)
        assert k1 != k2

    def test_build_cache_key_different_type(self):
        k1 = _build_cache_key("cats", "en", "photo", 720, 720, 1, 20)
        k2 = _build_cache_key("cats", "en", "illustration", 720, 720, 1, 20)
        assert k1 != k2

    def test_read_write_cache_roundtrip(self, tmp_path):
        cache_path = tmp_path / "test.json"
        hits = [_mock_hit(1), _mock_hit(2)]
        _write_cache(cache_path, hits)
        cached = _read_cache(cache_path, ttl_sec=86400)
        assert cached is not None
        assert len(cached) == 2
        assert cached[0]["id"] == 1

    def test_cache_expired_returns_none(self, tmp_path):
        cache_path = tmp_path / "test.json"
        hits = [_mock_hit(1)]
        _write_cache(cache_path, hits)
        time.sleep(0.1)
        cached = _read_cache(cache_path, ttl_sec=0)
        assert cached is None

    def test_cache_corrupt_returns_none(self, tmp_path):
        cache_path = tmp_path / "test.json"
        cache_path.write_text("not valid json", encoding="utf-8")
        cached = _read_cache(cache_path, ttl_sec=86400)
        assert cached is None

    def test_cache_missing_returns_none(self, tmp_path):
        cached = _read_cache(tmp_path / "nonexistent.json", ttl_sec=86400)
        assert cached is None

    def test_api_key_not_in_cache_content(self, tmp_path):
        cache_path = tmp_path / "test.json"
        hits = [_mock_hit(1)]
        _write_cache(cache_path, hits)
        content = cache_path.read_text(encoding="utf-8")
        assert "api_key" not in content.lower()


# ── Dimension helpers ────────────────────────────────────────────────────────


class TestDimensions:
    def test_expected_dimensions_no_scaling_needed(self):
        w, h = _calculate_expected_dimensions(800, 600, max_dim=1280)
        assert w == 800
        assert h == 600

    def test_expected_dimensions_landscape_scaled(self):
        w, h = _calculate_expected_dimensions(2560, 1440, max_dim=1280)
        assert w == 1280
        assert h == 720

    def test_expected_dimensions_portrait_scaled(self):
        w, h = _calculate_expected_dimensions(1000, 2000, max_dim=1280)
        assert w == 640
        assert h == 1280

    def test_expected_dimensions_exactly_max(self):
        w, h = _calculate_expected_dimensions(1280, 720, max_dim=1280)
        assert w == 1280
        assert h == 720

    def test_expected_dimensions_min_width_reject(self):
        w, h = _calculate_expected_dimensions(1200, 1000, max_dim=1280)
        assert w == 1200
        assert h == 1000
        assert w >= 720 and h >= 720

    def test_expected_dimensions_small_source(self):
        w, h = _calculate_expected_dimensions(400, 300, max_dim=1280)
        assert w == 400
        assert h == 300
        assert w < 720

    def test_expected_dimensions_zero(self):
        w, h = _calculate_expected_dimensions(0, 0, max_dim=1280)
        assert w == 0
        assert h == 0

    def test_expected_dimensions_negative(self):
        w, h = _calculate_expected_dimensions(-100, 200, max_dim=1280)
        assert w == 0
        assert h == 0


# ── Image dimension reading (stdlib) ─────────────────────────────────────────


class TestImageDimensions:
    def _sample_jpeg(self):
        soi = b"\xff\xd8"
        app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        sof0 = b"\xff\xc0\x00\x11\x08" + (300).to_bytes(2, "big") + (400).to_bytes(2, "big") + b"\x08"
        return soi + app0 + sof0 + b"\xff\xd9"

    def test_read_jpeg_dimensions(self, tmp_path):
        path = tmp_path / "test.jpg"
        path.write_bytes(self._sample_jpeg())
        mime = "image/jpeg"
        w, h = _read_image_dimensions(path, mime)
        assert w == 400
        assert h == 300

    def _sample_png(self):
        import struct
        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = b"IHDR" + struct.pack(">II", 500, 600) + b"\x08\x02\x00\x00\x00"
        crc = struct.pack(">I", 0)
        return sig + struct.pack(">I", 13) + ihdr + crc

    def test_read_png_dimensions(self, tmp_path):
        path = tmp_path / "test.png"
        path.write_bytes(self._sample_png())
        mime = "image/png"
        w, h = _read_image_dimensions(path, mime)
        assert w == 500
        assert h == 600

    def _sample_gif(self):
        return b"GIF89a" + (300).to_bytes(2, "little") + (200).to_bytes(2, "little") + b"\x00\x00\x00"

    def test_read_gif_dimensions(self, tmp_path):
        path = tmp_path / "test.gif"
        path.write_bytes(self._sample_gif())
        mime = "image/gif"
        w, h = _read_image_dimensions(path, mime)
        assert w == 300
        assert h == 200

    def test_read_dimensions_unknown_mime(self, tmp_path):
        path = tmp_path / "test.bin"
        path.write_bytes(b"not an image")
        w, h = _read_image_dimensions(path, "application/octet-stream")
        assert w == 0
        assert h == 0

    def test_read_dimensions_corrupt_file(self, tmp_path):
        path = tmp_path / "test.jpg"
        path.write_bytes(b"\xff\xd8\xff\xff")
        w, h = _read_image_dimensions(path, "image/jpeg")
        assert w == 0
        assert h == 0

    def test_read_webp_dimensions_vp8x(self, tmp_path):
        riff = b"RIFF"
        inner_size = (22).to_bytes(4, "little")
        webp_tag = b"WEBP"
        vp8x = b"VP8X"
        chunk_size = (10).to_bytes(4, "little")
        flags = b"\x00\x00\x00\x00"
        canvas_w = (799).to_bytes(3, "little")
        canvas_h = (599).to_bytes(3, "little")
        data = riff + inner_size + webp_tag + vp8x + chunk_size + flags + canvas_w + canvas_h
        path = tmp_path / "test.webp"
        path.write_bytes(data)
        w, h = _read_image_dimensions(path, "image/webp")
        assert w == 800
        assert h == 600

    def test_no_jpeg_magic(self):
        data = b"notajpeg"
        w, h = _read_jpeg_dimensions(data)
        assert w == 0
        assert h == 0

    def test_no_png_magic(self):
        data = b"notapngfile"
        w, h = _read_png_dimensions(data)
        assert w == 0
        assert h == 0

    def test_no_gif_magic(self):
        data = b"notagiffile"
        w, h = _read_gif_dimensions(data)
        assert w == 0
        assert h == 0

    def test_no_webp_magic(self):
        data = b"notawebpfile"
        w, h = _read_webp_dimensions(data)
        assert w == 0
        assert h == 0


# ── Resolve: API key validation ──────────────────────────────────────────────


class TestResolveApiKey:
    def test_missing_api_key_raises_value_error(self):
        with pytest.raises(ValueError, match="API key is required"):
            resolve_pixabay_candidates_v2(
                ["test"], api_key="", asset_preference="photograph",
            )

    def test_empty_api_key_raises(self):
        with pytest.raises(ValueError, match="API key is required"):
            resolve_pixabay_candidates_v2(
                ["test"], api_key="   ", asset_preference="photograph",
            )

    def test_unsupported_asset_pref_raises(self):
        with pytest.raises(ValueError, match="does not support"):
            resolve_pixabay_candidates_v2(
                ["test"], api_key="valid-key", asset_preference="archive",
            )


# ── Resolve: query encoding ──────────────────────────────────────────────────


class TestResolveQueryEncoding:
    def test_query_url_encoded_special_chars(self):
        with patch(
            "shorts_creator.assets.providers.pixabay._http_get_json",
            return_value=({"hits": [_mock_hit(1)], "totalHits": 1}, 200),
        ):
            candidates = resolve_pixabay_candidates_v2(
                ["café & croissants?"], api_key="KEY", asset_preference="photograph",
            )
        assert len(candidates) == 1

    def test_query_trimmed_to_200_chars(self):
        long_query = "x" * 300
        result = []
        def _mock(url, timeout):
            q = url.split("&q=")[1].split("&")[0] if "&q=" in url else ""
            pct = "q=" + "%78" * 200
            result.append(len(urllib.parse.unquote(q)) <= 200)
            return ({"hits": [_mock_hit(1)], "totalHits": 1}, 200)
        import urllib.parse
        with patch(
            "shorts_creator.assets.providers.pixabay._http_get_json",
            wraps=_mock,
        ):
            pass


# ── Resolve: image_type mapping ──────────────────────────────────────────────


class TestResolveImageTypeMapping:
    def test_photograph_uses_photo_type(self):
        requests_params = []
        def mock(url, timeout):
            import urllib.parse as up
            parsed = up.parse_qs(up.urlparse(url).query)
            requests_params.append(parsed)
            return ({"hits": [_mock_hit(1)], "totalHits": 1}, 200)
        with patch("shorts_creator.assets.providers.pixabay._http_get_json", wraps=mock):
            resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
            )
        assert any("image_type" in p for p in requests_params)
        for p in requests_params:
            if "image_type" in p:
                assert p["image_type"] == ["photo"]

    def test_stock_uses_photo_type(self):
        requests_params = []
        def mock(url, timeout):
            import urllib.parse as up
            parsed = up.parse_qs(up.urlparse(url).query)
            requests_params.append(parsed)
            return ({"hits": [_mock_hit(1)], "totalHits": 1}, 200)
        with patch("shorts_creator.assets.providers.pixabay._http_get_json", wraps=mock):
            resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="stock",
            )
        for p in requests_params:
            if "image_type" in p:
                assert p["image_type"] == ["photo"]

    def test_illustration_uses_illustration_type(self):
        requests_params = []
        def mock(url, timeout):
            import urllib.parse as up
            parsed = up.parse_qs(up.urlparse(url).query)
            requests_params.append(parsed)
            return ({"hits": [_mock_hit(1)], "totalHits": 1}, 200)
        with patch("shorts_creator.assets.providers.pixabay._http_get_json", wraps=mock):
            resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="illustration",
            )
        first_call_types = [p["image_type"] for p in requests_params if "image_type" in p]
        assert first_call_types[0] == ["illustration"]

    def test_diagram_uses_illustration_type(self):
        requests_params = []
        def mock(url, timeout):
            import urllib.parse as up
            parsed = up.parse_qs(up.urlparse(url).query)
            requests_params.append(parsed)
            return ({"hits": [_mock_hit(1)], "totalHits": 1}, 200)
        with patch("shorts_creator.assets.providers.pixabay._http_get_json", wraps=mock):
            resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="diagram",
            )
        first_call_types = [p["image_type"] for p in requests_params if "image_type" in p]
        assert first_call_types[0] == ["illustration"]


# ── Resolve: dimension and safesearch params ─────────────────────────────────


class TestResolveParams:
    def test_min_width_passed(self):
        params = []
        def mock(url, timeout):
            import urllib.parse as up
            p = up.parse_qs(up.urlparse(url).query)
            params.append(p)
            return ({"hits": [_mock_hit(1)], "totalHits": 1}, 200)
        with patch("shorts_creator.assets.providers.pixabay._http_get_json", wraps=mock):
            resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
                min_width=800,
            )
        for p in params:
            if "min_width" in p:
                assert p["min_width"] == ["800"]

    def test_min_height_passed(self):
        params = []
        def mock(url, timeout):
            import urllib.parse as up
            p = up.parse_qs(up.urlparse(url).query)
            params.append(p)
            return ({"hits": [_mock_hit(1)], "totalHits": 1}, 200)
        with patch("shorts_creator.assets.providers.pixabay._http_get_json", wraps=mock):
            resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
                min_height=800,
            )
        for p in params:
            if "min_height" in p:
                assert p["min_height"] == ["800"]

    def test_safesearch_true(self):
        params = []
        def mock(url, timeout):
            import urllib.parse as up
            p = up.parse_qs(up.urlparse(url).query)
            params.append(p)
            return ({"hits": [_mock_hit(1)], "totalHits": 1}, 200)
        with patch("shorts_creator.assets.providers.pixabay._http_get_json", wraps=mock):
            resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
            )
        for p in params:
            if "safesearch" in p:
                assert p["safesearch"] == ["true"]


# ── Resolve: result shaping ──────────────────────────────────────────────────


class TestResolveResultShape:
    def test_resolved_result_has_expected_fields(self):
        with patch(
            "shorts_creator.assets.providers.pixabay._http_get_json",
            return_value=({"hits": [_mock_hit(1)], "totalHits": 1}, 200),
        ):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
            )
        assert len(candidates) == 1
        c = candidates[0]
        assert c["provider"] == "pixabay"
        assert c["sourceUrl"] == "https://pixabay.com/photos/test-1/"
        assert c["fileUrl"] == "https://pixabay.com/get/test-1_1280.jpg"
        assert c["author"] == "TestUser"
        assert c["license"] == "Pixabay Content License"
        assert c["queryUsed"] == "test"
        assert c["providerRank"] == 1

    def test_source_url_comes_from_page_url(self):
        hit = _mock_hit(pageURL="https://pixabay.com/photos/my-photo-42/")
        with patch(
            "shorts_creator.assets.providers.pixabay._http_get_json",
            return_value=({"hits": [hit], "totalHits": 1}, 200),
        ):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
            )
        assert candidates[0]["sourceUrl"] == "https://pixabay.com/photos/my-photo-42/"

    def test_author_comes_from_user_field(self):
        hit = _mock_hit(user="johndoe")
        with patch(
            "shorts_creator.assets.providers.pixabay._http_get_json",
            return_value=({"hits": [hit], "totalHits": 1}, 200),
        ):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
            )
        assert candidates[0]["author"] == "johndoe"


# ── Resolve: error handling ──────────────────────────────────────────────────


class TestResolveErrors:
    def test_401_returns_empty_list(self):
        with patch(
            "shorts_creator.assets.providers.pixabay._http_get_json",
            return_value=(None, 401),
        ):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
            )
        assert candidates == []

    def test_403_returns_empty_list(self):
        with patch(
            "shorts_creator.assets.providers.pixabay._http_get_json",
            return_value=(None, 403),
        ):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
            )
        assert candidates == []

    def test_429_returns_empty_list(self):
        with patch(
            "shorts_creator.assets.providers.pixabay._http_get_json",
            return_value=(None, 429),
        ):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
            )
        assert candidates == []

    def test_timeout_returns_empty_list(self):
        with patch(
            "shorts_creator.assets.providers.pixabay._http_get_json",
            return_value=(None, None),
        ):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
            )
        assert candidates == []

    def test_zero_results_returns_empty_list(self):
        with patch(
            "shorts_creator.assets.providers.pixabay._http_get_json",
            return_value=({"hits": [], "totalHits": 0}, 200),
        ):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
            )
        assert candidates == []


# ── Resolve: excluded URLs ───────────────────────────────────────────────────


class TestResolveExcluded:
    def test_excluded_source_url_skipped(self):
        hits = [_mock_hit(1, pageURL="https://pixabay.com/photos/skip-me/"),
                _mock_hit(2, pageURL="https://pixabay.com/photos/use-me/")]
        with patch(
            "shorts_creator.assets.providers.pixabay._http_get_json",
            return_value=({"hits": hits, "totalHits": 2}, 200),
        ):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
                excluded_source_urls={"https://pixabay.com/photos/skip-me/"},
            )
        assert len(candidates) == 1
        assert candidates[0]["sourceUrl"] == "https://pixabay.com/photos/use-me/"

    def test_excluded_file_url_skipped(self):
        hits = [_mock_hit(1, largeImageURL="https://pixabay.com/get/skip.jpg"),
                _mock_hit(2, largeImageURL="https://pixabay.com/get/use.jpg")]
        with patch(
            "shorts_creator.assets.providers.pixabay._http_get_json",
            return_value=({"hits": hits, "totalHits": 2}, 200),
        ):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
                excluded_file_urls={"https://pixabay.com/get/skip.jpg"},
            )
        assert len(candidates) == 1
        assert candidates[0]["fileUrl"] == "https://pixabay.com/get/use.jpg"


# ── Resolve: cache behavior ──────────────────────────────────────────────────


class TestResolveCache:
    def test_cache_hit_no_http(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        # Cache all necessary pages
        import hashlib
        for page in range(1, 6):
            cache_key = _build_cache_key("test", "en", "photo", 720, 720, page, 20)
            cache_path = cache_dir / f"{cache_key}.json"
            hits = [_mock_hit(page)] if page == 1 else []
            _write_cache(cache_path, hits)

        call_count = [0]

        def mock(url, timeout):
            call_count[0] += 1
            return ({"hits": [], "totalHits": 0}, 200)

        with patch("shorts_creator.assets.providers.pixabay._http_get_json", wraps=mock):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
                cache_dir=cache_dir, cache_ttl_sec=86400,
            )
        assert len(candidates) >= 1
        assert call_count[0] == 0

    def test_cache_expired_renews(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        hits_old = [_mock_hit(1, user="OldUser")]
        cache_key = _build_cache_key("test", "en", "photo", 720, 720, 1, 20)
        cache_path = cache_dir / f"{cache_key}.json"
        _write_cache(cache_path, hits_old)

        call_count = [0]
        new_hits = [_mock_hit(1, user="NewUser")]

        def mock(url, timeout):
            call_count[0] += 1
            return ({"hits": new_hits, "totalHits": 1}, 200)

        with patch("shorts_creator.assets.providers.pixabay._http_get_json", wraps=mock):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
                cache_dir=cache_dir, cache_ttl_sec=0,
            )
        assert call_count[0] >= 1
        assert candidates[0]["author"] == "NewUser"

    def test_cache_corrupt_renews(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        cache_key = _build_cache_key("test", "en", "photo", 720, 720, 1, 20)
        cache_path = cache_dir / f"{cache_key}.json"
        cache_path.write_text("garbage data {{{", encoding="utf-8")

        call_count = [0]
        def mock(url, timeout):
            call_count[0] += 1
            return ({"hits": [_mock_hit(1)], "totalHits": 1}, 200)

        with patch("shorts_creator.assets.providers.pixabay._http_get_json", wraps=mock):
            candidates = resolve_pixabay_candidates_v2(
                ["test"], api_key="KEY", asset_preference="photograph",
                cache_dir=cache_dir, cache_ttl_sec=86400,
            )
        assert call_count[0] >= 1
        assert len(candidates) == 1


# ── Download: success ────────────────────────────────────────────────────────


class TestDownload:
    def test_download_local_asset(self, tmp_path):
        candidate = {
            "provider": "pixabay",
            "sourceUrl": "https://pixabay.com/photos/test/",
            "fileUrl": "https://pixabay.com/get/test_1280.jpg",
            "width": 1280,
            "height": 720,
            "author": "TestUser",
            "license": "Pixabay Content License",
        }
        output = tmp_path / "test.jpg"

        real_jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xc0\x00\x11\x08"
            + (720).to_bytes(2, "big")
            + (1280).to_bytes(2, "big")
            + b"\x08"
            + b"\xff\xda\x00\x00\x00\x00" + b"\x00" * 2000
            + b"\xff\xda" + b"\x00" * 2000
            + b"\xff\xd9"
        )

        def _mock_download(url, op, timeout=30):
            op.parent.mkdir(parents=True, exist_ok=True)
            op.write_bytes(real_jpeg)
            return True, "image/jpeg", len(real_jpeg)

        with patch("shorts_creator.assets.providers.pixabay._http_download", wraps=_mock_download):
            result = download_pixabay_asset_v2(candidate, output)
        assert result["ok"] is True, f"error: {result.get('error')}"
        assert output.exists()
        assert result["size"] > 0
        assert result["actualWidth"] == 1280
        assert result["actualHeight"] == 720

    def test_download_invalid_content_type_rejected(self, tmp_path):
        candidate = {
            "provider": "pixabay",
            "sourceUrl": "https://pixabay.com/photos/test/",
            "fileUrl": "https://pixabay.com/get/test_1280.jpg",
            "width": 1280,
            "height": 720,
        }
        output = tmp_path / "test.jpg"
        with patch(
            "shorts_creator.assets.providers.pixabay._http_download",
            return_value=(True, "application/pdf", 5000),
        ):
            result = download_pixabay_asset_v2(candidate, output)
        assert result["ok"] is False
        assert "invalid Content-Type" in result["error"]

    def test_download_dimensions_insufficient(self, tmp_path):
        candidate = {
            "provider": "pixabay",
            "sourceUrl": "https://pixabay.com/photos/test/",
            "fileUrl": "https://pixabay.com/get/test_1280.jpg",
            "width": 100,
            "height": 100,
        }
        output = tmp_path / "test.jpg"
        with patch(
            "shorts_creator.assets.providers.pixabay._http_download",
            return_value=(True, "image/jpeg", 5000),
        ):
            result = download_pixabay_asset_v2(candidate, output)
        assert result["ok"] is False
        assert "do not meet minimum" in result["error"]

    def test_download_file_too_small(self, tmp_path):
        candidate = {
            "provider": "pixabay",
            "sourceUrl": "https://pixabay.com/photos/test/",
            "fileUrl": "https://pixabay.com/get/test_1280.jpg",
            "width": 1280,
            "height": 720,
        }
        output = tmp_path / "test.jpg"
        with patch(
            "shorts_creator.assets.providers.pixabay._http_download",
            return_value=(True, "image/jpeg", 10),
        ):
            result = download_pixabay_asset_v2(candidate, output, min_size_bytes=100)
        assert result["ok"] is False
        assert "too small" in result["error"]

    def test_download_no_file_url(self, tmp_path):
        candidate = {
            "provider": "pixabay",
            "sourceUrl": "https://example.com",
            "fileUrl": "",
            "width": 1280,
            "height": 720,
        }
        result = download_pixabay_asset_v2(candidate, tmp_path / "test.jpg")
        assert result["ok"] is False
        assert "no fileUrl" in result["error"]


# ── No hotlinking ────────────────────────────────────────────────────────────


class TestNoHotlinking:
    def test_download_creates_local_file_not_hotlink(self, tmp_path):
        candidate = {
            "provider": "pixabay",
            "sourceUrl": "https://pixabay.com/photos/test/",
            "fileUrl": "https://pixabay.com/get/test_1280.jpg",
            "width": 1280,
            "height": 720,
        }
        output = tmp_path / "test.jpg"

        real_jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xc0\x00\x11\x08"
            + (720).to_bytes(2, "big")
            + (1280).to_bytes(2, "big")
            + b"\x08"
            + b"\xff\xda\x00\x00\x00\x00" + b"\x00" * 2000
            + b"\xff\xd9"
        )

        def _mock_download(url, op, timeout=30):
            op.parent.mkdir(parents=True, exist_ok=True)
            op.write_bytes(real_jpeg)
            return True, "image/jpeg", len(real_jpeg)

        with patch("shorts_creator.assets.providers.pixabay._http_download", wraps=_mock_download):
            result = download_pixabay_asset_v2(candidate, output)
        assert result["ok"] is True
        assert "pixabay" not in result["path"]
