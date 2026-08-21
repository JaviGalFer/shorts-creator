"""Static integration and security tests for web-ui-mvp Slice 4.

Verifies FastAPI + Angular production build integration with a
temporary fake Angular build directory injected via create_app().

Required tests (all must pass):
  1. /  returns exact index.html.
  2. /generator  falls back to exact index.html.
  3. /main-test.js  returns the actual JS contents and NOT index HTML.
  4. /styles-test.css  returns the actual CSS contents.
  5. unknown /api/v1/...  returns 404 and not HTML.
  6. unknown /api/...  returns 404 and not HTML.
  7. symlink escaping the frontend root is blocked (404, no content leak).
  8. configured missing frontend root: / -> 404, API health -> 200.
  8b. SHORTS_FRONTEND_DIST env resolves the browser build.
  8c. source-layout default is used without env or frontend_dist.
  9. create_app() used for API-only tests does not require Angular output.
 10. existing API routes continue taking precedence.
"""

from pathlib import Path
from fastapi.testclient import TestClient
from shorts_creator.web.app import create_app


def _make_fake_frontend(tmp_dir: Path) -> Path:
    """Create a minimal fake Angular browser build for testing."""
    browser = tmp_dir / "frontend" / "dist" / "frontend" / "browser"
    browser.mkdir(parents=True, exist_ok=True)
    (browser / "index.html").write_text(
        "<html><body>Fake Angular App</body></html>"
    )
    (browser / "main-test.js").write_text(
        "// fake angular entry point\nexport const APP_NAME = 'test';"
    )
    (browser / "styles-test.css").write_text(
        ".test { color: red; }"
    )
    return browser


def test_frontend_root_returns_index_html():
    """1. / returns exact index.html."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        browser = _make_fake_frontend(Path(tmp))
        app = create_app(frontend_dist=browser)
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "<html><body>Fake Angular App</body></html>" == resp.text


def test_spa_fallback_generator_route():
    """2. /generator falls back to exact index.html."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        browser = _make_fake_frontend(Path(tmp))
        app = create_app(frontend_dist=browser)
        client = TestClient(app)
        resp = client.get("/generator")
        assert resp.status_code == 200
        assert "<html><body>Fake Angular App</body></html>" == resp.text


def test_static_js_file_served():
    """3. /main-test.js returns the actual JS contents and NOT index HTML."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        browser = _make_fake_frontend(Path(tmp))
        app = create_app(frontend_dist=browser)
        client = TestClient(app)
        resp = client.get("/main-test.js")
        assert resp.status_code == 200
        assert "// fake angular entry point" in resp.text
        assert "<!doctype html>" not in resp.text


def test_static_css_file_served():
    """4. /styles-test.css returns the actual CSS contents."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        browser = _make_fake_frontend(Path(tmp))
        app = create_app(frontend_dist=browser)
        client = TestClient(app)
        resp = client.get("/styles-test.css")
        assert resp.status_code == 200
        assert ".test { color: red; }" in resp.text


def test_api_unknown_v1_returns_404():
    """5. unknown /api/v1/... returns 404 and not HTML."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        browser = _make_fake_frontend(Path(tmp))
        app = create_app(frontend_dist=browser)
        client = TestClient(app)
        resp = client.get("/api/v1/does-not-exist")
        assert resp.status_code == 404
        assert "<!doctype html>" not in resp.text


def test_api_unknown_returns_404():
    """6. unknown /api/... returns 404 and not HTML."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        browser = _make_fake_frontend(Path(tmp))
        app = create_app(frontend_dist=browser)
        client = TestClient(app)
        resp = client.get("/api/foo")
        assert resp.status_code == 404
        assert "<!doctype html>" not in resp.text


def test_traversal_blocked():
    """7. symlink escaping the frontend root is never followed."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        browser = _make_fake_frontend(tmp)

        # Create a secret file OUTSIDE the frontend root, then a symlink
        # INSIDE the frontend root pointing to it. Requesting the symlink
        # must return 404 and never leak the outside contents.
        secret = tmp / "outside-file.txt"
        secret.write_text("TOP-SECRET-OUTSIDE-CONTENT")
        (browser / "leak.txt").symlink_to(secret)

        app = create_app(frontend_dist=browser)
        client = TestClient(app)
        resp = client.get("/leak.txt")
        assert resp.status_code == 404
        assert "TOP-SECRET-OUTSIDE-CONTENT" not in resp.text


def test_missing_frontend_root_deterministic():
    """8. an actually nonexistent frontend root is deterministic: 404 + API intact."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        nonexistent = Path(tmp) / "does" / "not" / "exist"
        assert not nonexistent.exists()
        app = create_app(frontend_dist=nonexistent)
        client = TestClient(app)
        # Root: no frontend build present -> 404, never index.html
        resp = client.get("/")
        assert resp.status_code == 404
        # API health must still work
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200


def test_shorts_frontend_dist_env_resolution(monkeypatch):
    """8b. SHORTS_FRONTEND_DIST env resolves the browser build without frontend_dist."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        browser = _make_fake_frontend(Path(tmp))
        monkeypatch.setenv("SHORTS_FRONTEND_DIST", str(browser))
        app = create_app()
        client = TestClient(app)
        resp = client.get("/main-test.js")
        assert resp.status_code == 200
        assert "// fake angular entry point" in resp.text


def test_source_layout_default_resolution(monkeypatch):
    """8c. without env or frontend_dist, the source-layout default is used."""
    import tempfile
    monkeypatch.delenv("SHORTS_FRONTEND_DIST", raising=False)
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app()
        client = TestClient(app)
        # The real source-layout build exists on disk, so / serves index.html.
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.text.startswith("<!doctype html>") or "<html>" in resp.text


def test_api_tests_no_angular_requirement():
    """9. create_app() used for API-only tests does not require Angular output."""
    app = create_app()
    client = TestClient(app)
    # All API routes must be functional without any frontend configuration.
    resp = client.get("/api/v1/capabilities")
    assert resp.status_code == 200
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_api_precedence_over_frontend_fallback():
    """10. existing API routes take precedence over frontend fallback."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        browser = _make_fake_frontend(Path(tmp))
        app = create_app(frontend_dist=browser)
        client = TestClient(app)

        # API route must return its normal response, not index.html
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

        # Forward slash (frontend route) falls back to index.html
        resp = client.get("/")
        assert resp.status_code == 200
        assert "<html>" in resp.text

        # Unknown API path returns 404, not index.html
        resp = client.get("/api/v1/does-not-exist")
        assert resp.status_code == 404