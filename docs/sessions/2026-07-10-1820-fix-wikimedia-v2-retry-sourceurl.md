# Session: Fix Wikimedia v2 provider — HTTP 429 retry + sourceUrl separation

**Started:** 2026-07-10 1820 UTC
**Type:** Bounded correctness fix (Level 0)
**OpenSpec change:** None

## Objective

Two targeted fixes to the Wikimedia v2 provider module:

1. HTTP 429 retry was not implemented (line 46-59 of `_http_get_json` caught all HTTPError without checking the status code).
2. `sourceUrl` duplicated `fileUrl` — should be the Commons description page when possible.

## What was changed

### `bin/visual_provider_wikimedia_v2.py`

**Fix 1 — HTTP 429 retry:**

- `_http_get_json` now catches `urllib.error.HTTPError` specifically before the generic catch block.
- When `e.code == 429` and `retry_on_429` is `True`:
  - Sleeps for `retry_sleep_sec` seconds (default 1.0).
  - Creates a new `Request` object and retries once.
  - If retry succeeds, returns the decoded JSON.
  - If retry also fails with 429, returns `None`.
  - If retry fails with a different error, returns `None`.
- New parameters: `retry_on_429: bool = True`, `retry_sleep_sec: float = 1.0`.
- Non-429 HTTP errors still return `None` immediately without retry.
- All other exceptions (URLError, socket.timeout, JSONDecodeError, OSError, ValueError) are caught and return `None` without retry.

**Fix 2 — sourceUrl vs fileUrl separation:**

- `fileUrl` remains the direct downloadable image URL from `imageinfo.url`.
- `sourceUrl` is now built from the page title: `https://commons.wikimedia.org/wiki/{encoded_title}`.
- Uses `urllib.parse.quote(page_title, safe="/:")` to preserve the `File:` namespace colon.
- Falls back to empty string when page title is unavailable.
- Old behavior (sourceUrl == fileUrl) completely removed.

### `tests/test_visual_provider_wikimedia_v2.py`

**New test class: `TestHttp429Retry` (5 tests)**

| Test | Assertion |
|------|-----------|
| `test_429_retries_and_succeeds` | 429 on first URL open → sleep once → retry succeeds → candidate resolved |
| `test_429_calls_sleep_once_with_default_duration` | Sleep called once with 1.0s argument |
| `test_non_429_http_error_does_not_retry` | HTTP 500 → returns None, sleep never called |
| `test_429_retry_also_fails_returns_none` | Always 429 → both attempts fail → returns None |
| `test_user_agent_preserved_on_retry` | User-Agent header present on both the 429-causing request and the retry request |

**New test class: `TestSourceUrlFileUrlSeparation` (4 tests)**

| Test | Assertion |
|------|-----------|
| `test_source_url_is_commons_page_not_file_url` | sourceUrl starts with `https://commons.wikimedia.org/wiki/File:`, different from fileUrl |
| `test_source_url_handles_spaces_in_title` | Spaces in title are `%20`-encoded in sourceUrl |
| `test_source_url_empty_when_title_missing` | Empty title → None result (filtered earlier) |
| `test_file_url_remains_direct_download` | fileUrl contains `upload.wikimedia.org`, sourceUrl contains `wiki/File:` |

**Updated existing tests:**

- `TestResolveHappyPath.test_resolve_returns_candidate_from_first_query`: Now asserts `fileUrl` starts with `upload.wikimedia.org` and `sourceUrl` starts with `commons.wikimedia.org/wiki/File:`.
- `TestResolveMetadataFallbacks.test_no_extmetadata_defaults`: Title assertion updated to handle `File:` prefix from realistic search responses.
- `_search_response` helper: Now auto-prepends `File:` prefix to titles to simulate real Wikimedia API behavior.

## Files NOT changed

- `bin/visual_asset_executor_v2.py`
- `tests/test_visual_asset_executor_v2.py`
- `tests/test_visual_v2_dry_run_e2e.py`
- All v1 pipeline modules
- n8n workflows, README, OpenSpec, .env.example, requirements.txt

## Validation

```bash
python3 -m pytest tests/test_visual_provider_wikimedia_v2.py -v  # 43 passed
python3 -m pytest tests/ -v                                       # 665 passed
git diff --check                                                   # clean
```

## Remaining

No new dependencies. The pipeline integration path remains unchanged from the prior session.
