#!/usr/bin/env python3
"""Print the first sessionID found in an events.jsonl stream."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import events


def main():
    if len(sys.argv) < 2:
        print("usage: python3 session_id.py <events.jsonl>", file=sys.stderr)
        sys.exit(2)
    sid = events.first_session_id(sys.argv[1])
    if sid:
        print(sid)


if __name__ == "__main__":
    main()