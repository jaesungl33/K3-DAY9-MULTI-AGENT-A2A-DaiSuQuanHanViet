#!/usr/bin/env python3
"""
Try to download official EC_*.json inputs from the course upstream repo.
If found, overwrite input/ and print instructions to re-run main.py.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "input"

CANDIDATE_BASES = [
    "https://raw.githubusercontent.com/VinUni-AI20k/K3-Day9-Multi-Agent-A2A/main/input",
]


def fetch(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    except Exception:
        return None


def main() -> int:
    base = None
    sample = None
    for b in CANDIDATE_BASES:
        sample = fetch(f"{b}/EC_001.json")
        if sample:
            base = b
            break
    if not base:
        print("Official inputs not published yet.")
        print("Keep using scripts/generate_inputs.py for local runs.")
        return 2

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in INPUT_DIR.glob("EC_*.json"):
        old.unlink()

    ok = 0
    for i in range(1, 51):
        name = f"EC_{i:03d}.json"
        text = fetch(f"{base}/{name}")
        if not text:
            print(f"Missing {name} from upstream")
            return 1
        json.loads(text)  # validate JSON
        (INPUT_DIR / name).write_text(text, encoding="utf-8")
        ok += 1
    print(f"Downloaded {ok} official inputs from {base}")
    print("Next: python main.py && python scripts/pack_output.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
