#!/usr/bin/env python3
"""Generate sample input cases for local pipeline testing."""

from __future__ import annotations

import json
from pathlib import Path

SAMPLES = [
    ("EC_001", "canceled_order_paid", "1b9ecfe83cdc259250e1a8aca174f0ad"),
    ("EC_002", "unavailable_order_paid", "8e24261a7e58791d10cb1bf9da94df5c"),
    ("EC_003", "late_delivery_seller", "203096f03d82e0dffbc41ebc2e2bcfb7"),
    ("EC_004", "late_delivery_logistics", "fbf9ac61453ac646ce8ad9783d7d0af6"),
    ("EC_005", "valid_split_payment", "e481f51cbdc54678b7cc49136f2d6af7"),
    ("EC_006", "unsupported_late_claim", "53cdb2fc8bc7dce0b6741e2150273451"),
]

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"


def main() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    for case_id, _label, order_id in SAMPLES:
        payload = {
            "case_id": case_id,
            "opened_at": "2018-10-18T00:00:00-03:00",
            "customer_request": {
                "language": "vi",
                "message": "Đơn hàng của tôi có vấn đề. Hãy kiểm tra nguyên nhân và quyền lợi phù hợp.",
                "claimed_order_id": order_id,
            },
            "policy_version": "EC_POLICY_V1",
        }
        path = INPUT_DIR / f"{case_id}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
