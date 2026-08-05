#!/usr/bin/env python3
"""
Generate 50 EC_*.json input cases from Olist covering all EC_POLICY_V1 issue types.

Use this when official Checkpoint-1 inputs are not yet available, or for local smoke tests.
When official inputs arrive, replace files under input/ and re-run main.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import INPUT_DIR, PAYMENT_MATCH_TOLERANCE_BRL
from src.data.policy import apply_policy, is_delivery_late, payments_match_items, seller_handoff_late
from src.data.store import get_store

MESSAGES = {
    "canceled_order_paid": "Đơn hàng bị hủy nhưng tôi đã thanh toán. Xin hoàn tiền toàn bộ.",
    "unavailable_order_paid": "Đơn hàng unavailable dù đã thanh toán. Đề nghị hoàn tiền.",
    "late_delivery_seller": "Đơn hàng giao trễ. Tôi nghi seller bàn giao chậm cho đơn vị vận chuyển.",
    "late_delivery_logistics": "Đơn hàng giao trễ dù seller đã bàn giao đúng hạn. Kiểm tra logistics.",
    "valid_split_payment": "Tôi thấy nhiều dòng thanh toán trên đơn. Có bị tính trùng không?",
    "unsupported_late_claim": "Đơn hàng của tôi có dấu hiệu giao trễ. Hãy kiểm tra nguyên nhân và quyền lợi phù hợp.",
}

TARGET_COUNTS = {
    "canceled_order_paid": 8,
    "unavailable_order_paid": 8,
    "late_delivery_seller": 10,
    "late_delivery_logistics": 10,
    "valid_split_payment": 7,
    "unsupported_late_claim": 7,
}


def classify(bundle) -> str:
    return apply_policy(bundle).primary_issue


def collect_candidates(store, limit_scan: int = 80000):
    buckets: dict[str, list[str]] = {k: [] for k in TARGET_COUNTS}
    order_ids = list(store._orders_by_id.keys())
    for oid in order_ids[:limit_scan]:
        bundle = store.get_order_bundle(oid)
        if bundle is None:
            continue
        issue = classify(bundle)
        if issue in buckets and len(buckets[issue]) < TARGET_COUNTS[issue] + 5:
            # Prefer cases that actually have payments for refund scenarios
            if issue in ("canceled_order_paid", "unavailable_order_paid") and bundle.payment_total_brl <= 0:
                continue
            buckets[issue].append(oid)
        if all(len(buckets[k]) >= TARGET_COUNTS[k] for k in TARGET_COUNTS):
            break
    return buckets


def write_inputs(buckets: dict[str, list[str]], out_dir: Path = INPUT_DIR) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    # remove old EC files
    for old in out_dir.glob("EC_*.json"):
        old.unlink()

    selected: list[tuple[str, str]] = []
    for issue, n in TARGET_COUNTS.items():
        ids = buckets.get(issue, [])[:n]
        if len(ids) < n:
            raise RuntimeError(f"Not enough candidates for {issue}: got {len(ids)}, need {n}")
        for oid in ids:
            selected.append((issue, oid))

    # Stable order: fill EC_001..EC_050
    case_ids = []
    for idx, (issue, oid) in enumerate(selected, start=1):
        case_id = f"EC_{idx:03d}"
        case = {
            "case_id": case_id,
            "opened_at": "2018-10-18T00:00:00-03:00",
            "customer_request": {
                "language": "vi",
                "message": MESSAGES[issue],
                "claimed_order_id": oid,
            },
            "policy_version": "EC_POLICY_V1",
        }
        path = out_dir / f"{case_id}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        case_ids.append(case_id)
    return case_ids


def main() -> int:
    store = get_store()
    print("Scanning Olist for EC_POLICY_V1 candidates...")
    buckets = collect_candidates(store)
    for k, v in buckets.items():
        print(f"  {k}: {len(v)} candidates")
    case_ids = write_inputs(buckets)
    print(f"Wrote {len(case_ids)} inputs to {INPUT_DIR}")
    # sanity: re-classify first few
    for i in range(1, 4):
        case = json.loads((INPUT_DIR / f"EC_{i:03d}.json").read_text(encoding="utf-8"))
        b = store.get_order_bundle(case["customer_request"]["claimed_order_id"])
        print(f"  {case['case_id']} -> {classify(b)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
