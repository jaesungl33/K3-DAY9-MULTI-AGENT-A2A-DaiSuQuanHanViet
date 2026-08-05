from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecommerce_a2a.orchestrator import validate_project


if __name__ == "__main__":
    errors = validate_project(PROJECT_ROOT)
    if errors:
        print("PROJECT INVALID")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(2)
    print("PROJECT VALID: ready to run all 50 cases.")
