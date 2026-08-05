"""Validate all output JSON against schema, policy, and Olist data."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.policy import (  # noqa: E402
    apply_policy,
    is_delivery_late,
    payments_match_items,
    seller_handoff_late,
)
from src.data.store import get_store  # noqa: E402

VALID_ISSUES = {
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
}
CAUSE_MAP = {
    "canceled_order_paid": "ORDER_CANCELED_AFTER_PAYMENT",
    "unavailable_order_paid": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
    "late_delivery_seller": "SELLER_HANDOFF_AFTER_LIMIT",
    "late_delivery_logistics": "CARRIER_DELIVERED_AFTER_ESTIMATE",
    "valid_split_payment": "MULTIPLE_PAYMENTS_RECONCILED",
    "unsupported_late_claim": "DELIVERY_WITHIN_ESTIMATE",
}
ACTION_MAP = {
    "canceled_order_paid": "issue_full_refund",
    "unavailable_order_paid": "issue_full_refund",
    "late_delivery_seller": "refund_freight",
    "late_delivery_logistics": "refund_freight",
    "valid_split_payment": "explain_valid_split_payment",
    "unsupported_late_claim": "reject_late_refund",
}
EV_RE = {
    "order": re.compile(r"^order:[^:]+$"),
    "item": re.compile(r"^item:[^:]+:\d+$"),
    "payment": re.compile(r"^payment:[^:]+:\d+$"),
    "seller": re.compile(r"^seller:[^:]+$"),
    "policy": re.compile(r"^policy:[A-Z0-9_]+$"),
}


def main() -> int:
    store = get_store()
    issues: list[str] = []
    warns: list[str] = []
    by_issue: Counter[str] = Counter()

    for i in range(1, 51):
        cid = f"EC_{i:03d}"
        inp = json.loads((ROOT / "input" / f"{cid}.json").read_text(encoding="utf-8"))
        out = json.loads((ROOT / "output" / f"{cid}.json").read_text(encoding="utf-8"))
        oid = inp["customer_request"]["claimed_order_id"]
        bundle = store.get_order_bundle(oid)
        if bundle is None:
            issues.append(f"{cid}: order not found {oid}")
            continue

        expected = apply_policy(bundle)
        assessment = out["assessment"]
        by_issue[assessment["primary_issue"]] += 1

        if out.get("case_id") != cid:
            issues.append(f"{cid}: case_id mismatch")
        if assessment["primary_issue"] not in VALID_ISSUES:
            issues.append(f"{cid}: bad primary_issue")
        if assessment["primary_issue"] != expected.primary_issue:
            issues.append(
                f"{cid}: primary_issue {assessment['primary_issue']} != {expected.primary_issue}"
            )
        if assessment["case_status"] not in ("action_required", "no_action"):
            issues.append(f"{cid}: bad case_status")
        if not (0 <= float(assessment["confidence"]) <= 1):
            issues.append(f"{cid}: confidence out of range")

        entities = out["affected_entities"]
        for key in ("order_ids", "item_ids", "seller_ids", "payment_ids"):
            if len(entities.get(key, [])) > 5:
                issues.append(f"{cid}: {key} >5")
        if entities["order_ids"] != [oid]:
            issues.append(f"{cid}: order_ids mismatch")

        if not bundle.items:
            if entities["item_ids"] or entities["seller_ids"]:
                issues.append(f"{cid}: empty items but entities non-empty")
            fin0 = out["financial_resolution"]
            if fin0["item_total_brl"] != 0.0 or fin0["freight_total_brl"] != 0.0:
                issues.append(f"{cid}: no items but totals not 0")

        for iid in entities["item_ids"]:
            parts = iid.split(":")
            if len(parts) != 2 or parts[0] != oid:
                issues.append(f"{cid}: bad item_id {iid}")
                continue
            if not any(str(it["order_item_id"]) == parts[1] for it in bundle.items):
                issues.append(f"{cid}: item_id not in data {iid}")

        for sid in entities["seller_ids"]:
            if sid not in [it.get("seller_id") for it in bundle.items]:
                issues.append(f"{cid}: seller_id not in items {sid}")

        for pid in entities["payment_ids"]:
            parts = pid.split(":")
            if len(parts) != 2 or parts[0] != oid:
                issues.append(f"{cid}: bad payment_id {pid}")
                continue
            if not any(str(p["payment_sequential"]) == parts[1] for p in bundle.payments):
                issues.append(f"{cid}: payment_id not in data {pid}")

        rca = out["root_cause_analysis"]
        if len(rca["ranked_causes"]) > 3 or len(rca["responsible_parties"]) > 3:
            issues.append(f"{cid}: rca limits")
        cause = rca["ranked_causes"][0]["cause_code"] if rca["ranked_causes"] else None
        if cause != CAUSE_MAP[assessment["primary_issue"]]:
            issues.append(f"{cid}: cause mismatch issue")
        if cause != expected.cause_code:
            issues.append(f"{cid}: cause != policy expected")
        if rca["responsible_parties"] != expected.responsible_parties[:3]:
            issues.append(
                f"{cid}: parties {rca['responsible_parties']} != {expected.responsible_parties}"
            )

        evidence = out["evidence_ids"]
        if len(evidence) > 10:
            issues.append(f"{cid}: evidence >10")
        if len(evidence) != len(set(evidence)):
            issues.append(f"{cid}: duplicate evidence")
        for eid in evidence:
            kind = eid.split(":", 1)[0]
            pat = EV_RE.get(kind)
            if not pat or not pat.match(eid):
                issues.append(f"{cid}: bad evidence format {eid}")
                continue
            if kind == "order" and eid != f"order:{oid}":
                issues.append(f"{cid}: evidence order mismatch {eid}")
            elif kind == "item":
                _, order_id, num = eid.split(":")
                if order_id != oid or not any(
                    str(it["order_item_id"]) == num for it in bundle.items
                ):
                    issues.append(f"{cid}: evidence item not in data {eid}")
            elif kind == "payment":
                _, order_id, num = eid.split(":")
                if order_id != oid or not any(
                    str(p["payment_sequential"]) == num for p in bundle.payments
                ):
                    issues.append(f"{cid}: evidence payment not in data {eid}")
            elif kind == "seller":
                sid = eid.split(":", 1)[1]
                if sid not in [it.get("seller_id") for it in bundle.items]:
                    issues.append(f"{cid}: evidence seller not in data {eid}")
            elif kind == "policy" and eid != f"policy:{cause}":
                warns.append(f"{cid}: policy evidence {eid} vs cause {cause}")

        fin = out["financial_resolution"]
        if fin["currency"] != "BRL":
            issues.append(f"{cid}: currency")
        for key in (
            "item_total_brl",
            "freight_total_brl",
            "payment_total_brl",
            "recommended_refund_brl",
        ):
            value = float(fin[key])
            if round(value, 2) != value:
                issues.append(f"{cid}: {key} not 2dp {value}")
        if abs(fin["item_total_brl"] - bundle.item_total_brl) > 1e-9:
            issues.append(f"{cid}: item_total mismatch")
        if abs(fin["freight_total_brl"] - bundle.freight_total_brl) > 1e-9:
            issues.append(f"{cid}: freight mismatch")
        if abs(fin["payment_total_brl"] - bundle.payment_total_brl) > 1e-9:
            issues.append(f"{cid}: payment mismatch")
        if abs(fin["recommended_refund_brl"] - expected.recommended_refund_brl) > 1e-9:
            issues.append(f"{cid}: refund mismatch")

        if fin["recommended_refund_brl"] > 0 and assessment["case_status"] != "action_required":
            issues.append(f"{cid}: refund>0 but no_action")
        if fin["recommended_refund_brl"] == 0 and assessment["case_status"] != "no_action":
            issues.append(f"{cid}: refund=0 but action_required")

        actions = out["resolution_actions"]
        if len(actions) > 5:
            issues.append(f"{cid}: actions >5")
        expected_action = [ACTION_MAP[assessment["primary_issue"]]]
        if actions != expected_action:
            issues.append(f"{cid}: actions {actions} expected {expected_action}")

        issue = assessment["primary_issue"]
        if issue == "canceled_order_paid":
            if bundle.order_status != "canceled" or bundle.payment_total_brl <= 0:
                issues.append(f"{cid}: canceled rule broken")
        elif issue == "unavailable_order_paid":
            if bundle.order_status != "unavailable" or bundle.payment_total_brl <= 0:
                issues.append(f"{cid}: unavailable rule broken")
        elif issue == "late_delivery_seller":
            late = is_delivery_late(bundle)
            seller_late, _ = seller_handoff_late(bundle)
            if not (late and seller_late):
                issues.append(f"{cid}: late_seller rule broken")
        elif issue == "late_delivery_logistics":
            late = is_delivery_late(bundle)
            seller_late, _ = seller_handoff_late(bundle)
            if not (late and not seller_late):
                issues.append(f"{cid}: late_logistics rule broken")
        elif issue == "valid_split_payment":
            if not (len(bundle.payments) >= 2 and payments_match_items(bundle)):
                issues.append(f"{cid}: split rule broken")
        elif issue == "unsupported_late_claim":
            if is_delivery_late(bundle) or not payments_match_items(bundle):
                issues.append(f"{cid}: unsupported rule broken")

    print("=== SUMMARY ===")
    print("by_issue", dict(by_issue))
    print("errors", len(issues))
    print("warns", len(warns))
    for item in issues[:40]:
        print("ERR", item)
    for item in warns[:10]:
        print("WARN", item)
    if not issues:
        print("ALL 50 OUTPUTS PASS schema + policy + data consistency checks")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
