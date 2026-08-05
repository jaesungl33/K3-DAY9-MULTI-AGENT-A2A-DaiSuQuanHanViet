#!/usr/bin/env python3
"""Entry point: resolve all EC_* cases under input/ into output/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline import run_pipeline


def main() -> int:
    summary = run_pipeline()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
