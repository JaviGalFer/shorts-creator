"""Architecture checks for the migrated Visual Assets V2 domain."""

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "bin"))

import fetch_images_v2 as cli
from shorts_creator.assets import fetcher


def test_assets_domain_is_importable():
    assert callable(fetcher.fetch_assets)


def test_cli_delegates_explicit_arguments(monkeypatch):
    received = {}

    def fake_fetch_assets(**kwargs):
        received.update(kwargs)
        return 7

    monkeypatch.setattr(fetcher, "fetch_assets", fake_fetch_assets)

    assert cli.main(["metadata.json", "--dry-run"]) == 7
    assert received == {
        "metadata_path": "metadata.json",
        "dry_run": True,
        "user_agent": None,
    }


def test_internal_asset_modules_are_absent_from_bin():
    removed = [
        "visual_asset_router_v2.py",
        "visual_asset_executor_v2.py",
        "visual_asset_bridge_v2.py",
        "visual_asset_renderability_v2.py",
        "visual_provider_config_v2.py",
        "visual_provider_wikimedia_v2.py",
        "visual_provider_pixabay_v2.py",
    ]
    assert not [name for name in removed if (PROJECT / "bin" / name).exists()]


def test_fetch_cli_contains_no_asset_runtime():
    source = (PROJECT / "bin" / "fetch_images_v2.py").read_text()
    forbidden = [
        "def _process_scene",
        "def _atomic_write",
        "build_visual_sourcing_plan_v2",
        "execute_visual_sourcing_plan_v2",
        "load_provider_config_v2",
        "apply_visual_assets_v2_to_metadata",
    ]
    assert not [token for token in forbidden if token in source]
