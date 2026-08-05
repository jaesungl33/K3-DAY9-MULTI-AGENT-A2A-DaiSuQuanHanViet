#!/usr/bin/env python3
"""CLI entry point for the multi-agent dispute resolution pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.orchestrator import INPUT_DIR, OUTPUT_DIR, process_all


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Olist multi-agent dispute resolution")
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    if not any(args.input_dir.glob("EC_*.json")):
        print(f"No case files found in {args.input_dir}", file=sys.stderr)
        return 1

    processed = process_all(args.input_dir, args.output_dir)
    print(f"Processed {len(processed)} cases -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
