"""JSON metadata persistence for the V2 runtime."""

from __future__ import annotations

import json


def load_metadata(path: str) -> dict:
    with open(path, "r") as file:
        return json.load(file)


def save_metadata(path: str, data: dict) -> None:
    with open(path, "w") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")
