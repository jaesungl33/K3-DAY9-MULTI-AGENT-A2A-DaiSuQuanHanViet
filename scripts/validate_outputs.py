"""Independently validate all submitted outputs against EC_POLICY_V1 and Olist CSVs."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
DATA_DIR = ROOT / "data"

EXPECTED_CASES = {f"EC_{index:03d}" for index in range(1, 51)}
ISSUE_RULES = {
    "canceled_order_paid": (
        "action_required",
        "ORDER_CANCELED_AFTER_PAYMENT",
        "issue_full_refund",
    ),
    "unavailable_order_paid": (
        "action_required",
        "ORDER_UNAVAILABLE_AFTER_PAYMENT",
        "issue_full_refund",
    ),
    "late_delivery_seller": (
        "action_required",
        "SELLER_HANDOFF_AFTER_LIMIT",
        "refund_freight",
    ),
    "late_delivery_logistics": (
        "action_required",
        "CARRIER_DELIVERED_AFTER_ESTIMATE",
        "refund_freight",
    ),
    "valid_split_payment": (
        "no_action",
        "MULTIPLE_PAYMENTS_RECONCILED",
        "explain_valid_split_payment",
    ),
    "unsupported_late_claim": (
        "no_action",
        "DELIVERY_WITHIN_ESTIMATE",
        "reject_late_refund",
    ),
}


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def money(value: float) -> float:
    return round(float(value) + 1e-12, 2)


def timestamp(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def expected_decision(
    order: dict[str, str] | None,
    items: list[dict[str, str]],
    payments: list[dict[str, str]],
) -> dict[str, Any]:
    item_total = money(sum(float(row["price"]) for row in items))
    freight_total = money(sum(float(row["freight_value"]) for row in items))
    payment_total = money(sum(float(row["payment_value"]) for row in payments))
    payment_matches = abs(payment_total - money(item_total + freight_total)) <= 0.10

    seller_late = False
    violating_seller = None
    if order:
        carrier_date = timestamp(order.get("order_delivered_carrier_date"))
        for item in items:
            limit_date = timestamp(item.get("shipping_limit_date"))
            if carrier_date and limit_date and carrier_date > limit_date:
                seller_late = True
                violating_seller = item["seller_id"]
                break

    delivered_late = False
    if order:
        delivered = timestamp(order.get("order_delivered_customer_date"))
        estimated = timestamp(order.get("order_estimated_delivery_date"))
        delivered_late = bool(delivered and estimated and delivered > estimated)

    status = (order or {}).get("order_status", "").lower()
    if status == "canceled" and payment_total > 0:
        issue, refund = "canceled_order_paid", payment_total
    elif status == "unavailable" and payment_total > 0:
        issue, refund = "unavailable_order_paid", payment_total
    elif delivered_late and seller_late:
        issue, refund = "late_delivery_seller", freight_total
    elif delivered_late and not seller_late:
        issue, refund = "late_delivery_logistics", freight_total
    elif len(payments) >= 2 and payment_matches:
        issue, refund = "valid_split_payment", 0.0
    else:
        issue, refund = "unsupported_late_claim", 0.0

    case_status, cause, action = ISSUE_RULES[issue]
    if issue == "late_delivery_seller":
        parties = [{"party_type": "seller", "party_id": violating_seller}]
    elif issue in {"canceled_order_paid", "unavailable_order_paid"}:
        parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
    elif issue == "late_delivery_logistics":
        parties = [
            {"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}
        ]
    else:
        parties = []

    return {
        "issue": issue,
        "case_status": case_status,
        "cause": cause,
        "parties": parties,
        "action": action,
        "item_total": item_total,
        "freight_total": freight_total,
        "payment_total": payment_total,
        "refund": money(refund),
    }


def add_error(errors: dict[str, list[str]], case_id: str, message: str) -> None:
    errors[case_id].append(message)


def validate_case(
    case_id: str,
    input_data: dict[str, Any],
    output: dict[str, Any],
    orders: dict[str, dict[str, str]],
    items_by_order: dict[str, list[dict[str, str]]],
    payments_by_order: dict[str, list[dict[str, str]]],
    seller_ids: set[str],
    errors: dict[str, list[str]],
) -> str:
    order_id = input_data["customer_request"]["claimed_order_id"]
    order = orders.get(order_id)
    items = sorted(items_by_order.get(order_id, []), key=lambda row: int(row["order_item_id"]))
    payments = sorted(
        payments_by_order.get(order_id, []), key=lambda row: int(row["payment_sequential"])
    )
    expected = expected_decision(order, items, payments)

    required = {
        "case_id",
        "assessment",
        "affected_entities",
        "root_cause_analysis",
        "evidence_ids",
        "financial_resolution",
        "resolution_actions",
    }
    if not required.issubset(output):
        add_error(errors, case_id, f"missing top-level keys: {sorted(required - output.keys())}")
        return expected["issue"]

    if output["case_id"] != case_id:
        add_error(errors, case_id, "case_id does not match filename")

    assessment = output["assessment"]
    if assessment.get("primary_issue") != expected["issue"]:
        add_error(errors, case_id, "primary_issue differs from EC_POLICY_V1")
    if assessment.get("case_status") != expected["case_status"]:
        add_error(errors, case_id, "case_status differs from refund decision")
    confidence = assessment.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        add_error(errors, case_id, "confidence is outside [0, 1]")

    entities = output["affected_entities"]
    expected_entities = {
        "order_ids": [order_id] if order else [],
        "item_ids": [f'{order_id}:{row["order_item_id"]}' for row in items[:5]],
        "seller_ids": list(dict.fromkeys(row["seller_id"] for row in items))[:5],
        "payment_ids": [f'{order_id}:{row["payment_sequential"]}' for row in payments[:5]],
    }
    for key, expected_values in expected_entities.items():
        values = entities.get(key)
        if values != expected_values:
            add_error(errors, case_id, f"{key} does not match source rows")
        if not isinstance(values, list) or len(values) > 5:
            add_error(errors, case_id, f"{key} exceeds schema limit or is not a list")

    root_cause = output["root_cause_analysis"]
    expected_causes = [{"cause_code": expected["cause"], "rank": 1}]
    if root_cause.get("ranked_causes") != expected_causes:
        add_error(errors, case_id, "ranked cause differs from policy decision")
    if root_cause.get("responsible_parties") != expected["parties"]:
        add_error(errors, case_id, "responsible party differs from policy decision")
    if len(root_cause.get("ranked_causes", [])) > 3:
        add_error(errors, case_id, "root cause limit exceeded")
    if len(root_cause.get("responsible_parties", [])) > 3:
        add_error(errors, case_id, "responsible party limit exceeded")

    valid_evidence = {f"order:{order_id}"} if order else set()
    valid_evidence.update(f'item:{order_id}:{row["order_item_id"]}' for row in items)
    valid_evidence.update(f'seller:{row["seller_id"]}' for row in items)
    valid_evidence.update(f'payment:{order_id}:{row["payment_sequential"]}' for row in payments)
    valid_evidence.add(f'policy:{expected["cause"]}')
    evidence = output["evidence_ids"]
    if not isinstance(evidence, list) or len(evidence) > 10:
        add_error(errors, case_id, "evidence limit exceeded or evidence_ids is not a list")
    else:
        for evidence_id in evidence:
            if evidence_id.startswith("seller:") and evidence_id.split(":", 1)[1] not in seller_ids:
                add_error(errors, case_id, f"unknown seller evidence: {evidence_id}")
            elif evidence_id not in valid_evidence:
                add_error(errors, case_id, f"invalid or irrelevant evidence: {evidence_id}")
        if f'policy:{expected["cause"]}' not in evidence:
            add_error(errors, case_id, "policy evidence is missing")

    financial = output["financial_resolution"]
    expected_financial = {
        "currency": "BRL",
        "item_total_brl": expected["item_total"],
        "freight_total_brl": expected["freight_total"],
        "payment_total_brl": expected["payment_total"],
        "recommended_refund_brl": expected["refund"],
    }
    if financial != expected_financial:
        add_error(errors, case_id, "financial resolution differs from CSV totals/policy")

    actions = output["resolution_actions"]
    if actions != [expected["action"]]:
        add_error(errors, case_id, "resolution action differs from policy decision")
    if not isinstance(actions, list) or len(actions) > 5:
        add_error(errors, case_id, "action limit exceeded or actions is not a list")

    return expected["issue"]


def main() -> int:
    input_files = {path.stem: path for path in INPUT_DIR.glob("EC_*.json")}
    output_files = {path.stem: path for path in OUTPUT_DIR.glob("EC_*.json")}
    errors: dict[str, list[str]] = defaultdict(list)

    if set(input_files) != EXPECTED_CASES:
        errors["FILES"].append("input/ does not contain exactly EC_001..EC_050")
    if set(output_files) != EXPECTED_CASES:
        errors["FILES"].append("output/ does not contain exactly EC_001..EC_050")
    unexpected = [path.name for path in OUTPUT_DIR.iterdir() if path.is_file() and path.suffix != ".json"]
    if unexpected:
        errors["FILES"].append(f"unexpected non-JSON files in output/: {unexpected}")

    order_rows = read_csv("olist_orders_dataset.csv")
    item_rows = read_csv("olist_order_items_dataset.csv")
    payment_rows = read_csv("olist_order_payments_dataset.csv")
    seller_rows = read_csv("olist_sellers_dataset.csv")

    orders = {row["order_id"]: row for row in order_rows}
    items_by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
    payments_by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in item_rows:
        items_by_order[row["order_id"]].append(row)
    for row in payment_rows:
        payments_by_order[row["order_id"]].append(row)
    seller_ids = {row["seller_id"] for row in seller_rows}

    issue_counts: Counter[str] = Counter()
    for case_id in sorted(EXPECTED_CASES & set(input_files) & set(output_files)):
        try:
            issue = validate_case(
                case_id,
                read_json(input_files[case_id]),
                read_json(output_files[case_id]),
                orders,
                items_by_order,
                payments_by_order,
                seller_ids,
                errors,
            )
            issue_counts[issue] += 1
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            add_error(errors, case_id, f"cannot validate malformed data: {exc}")

    failed_cases = sorted(case_id for case_id in errors if case_id != "FILES")
    summary = {
        "checked_cases": len(EXPECTED_CASES & set(input_files) & set(output_files)),
        "passed_cases": 50 - len(failed_cases) if not errors.get("FILES") else 0,
        "failed_cases": failed_cases,
        "issue_distribution": dict(sorted(issue_counts.items())),
        "file_errors": errors.get("FILES", []),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        print("\nValidation errors:")
        for case_id in sorted(errors):
            for message in errors[case_id]:
                print(f"- {case_id}: {message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
