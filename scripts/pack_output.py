#!/usr/bin/env python3
"""Zip output/ into output_submission.zip containing only EC_001..EC_050.json."""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
ZIP_PATH = ROOT / "output_submission.zip"


def main() -> int:
    files = sorted(OUTPUT.glob("EC_*.json"))
    if len(files) != 50:
        raise SystemExit(f"Expected 50 output JSON files, found {len(files)}")
    expected = {f"EC_{i:03d}.json" for i in range(1, 51)}
    names = {p.name for p in files}
    if names != expected:
        missing = sorted(expected - names)
        extra = sorted(names - expected)
        raise SystemExit(f"Output set mismatch. missing={missing} extra={extra}")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, arcname=path.name)
    print(f"Created {ZIP_PATH} with {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
