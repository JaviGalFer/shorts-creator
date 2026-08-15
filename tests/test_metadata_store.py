"""Tests for canonical JSON metadata persistence."""

import sys
from pathlib import Path

PROJECT = Path("/home/javi/projects/shorts-creator")
sys.path.insert(0, str(PROJECT / "bin"))

import run_job
from shorts_creator.infrastructure import metadata_store


def test_metadata_store_round_trip(tmp_path):
    path = tmp_path / "metadata.json"
    data = {"title": "Espana", "nested": {"count": 2}}

    metadata_store.save_metadata(str(path), data)

    assert metadata_store.load_metadata(str(path)) == data


def test_metadata_store_preserves_json_formatting_and_unicode(tmp_path):
    path = tmp_path / "metadata.json"

    metadata_store.save_metadata(str(path), {"title": "camaleón"})

    assert path.read_text(encoding="utf-8") == '{\n  "title": "camaleón"\n}\n'


def test_run_job_reexports_canonical_metadata_store_functions():
    assert run_job.load_metadata is metadata_store.load_metadata
    assert run_job.save_metadata is metadata_store.save_metadata
