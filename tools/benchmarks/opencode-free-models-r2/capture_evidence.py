#!/usr/bin/env python3
"""Print capture-evidence status for an events.jsonl stream:
'complete', 'no_text', 'no_step_finish', or 'incomplete'.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import events


def main():
    if len(sys.argv) < 2:
        print("usage: python3 capture_evidence.py <events.jsonl>", file=sys.stderr)
        sys.exit(2)
    ev = events.capture_evidence(sys.argv[1])
    if ev["complete"]:
        print("complete")
    elif not ev["has_text"] and not ev["has_step_end"]:
        print("incomplete")
    elif not ev["has_text"]:
        print("no_text")
    else:
        print("no_step_finish")


if __name__ == "__main__":
    main()