"""EC_POLICY_V1 deterministic rule engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from src.config import MONEY_ROUND, PAYMENT_MATCH_TOLERANCE_BRL
from src.data.store import OrderBundle


def _round_money(value: float) -> float:
    return round(float(value), MONEY_ROUND)


def _to_ts(value: Any) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value
    if isinstance(value, datetime):
        return pd.Timestamp(value)
    ts = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(ts) else ts


@dataclass
class PolicyDecision:
    primary_issue: str
    case_status: str
    confidence: float
    cause_code: str
    responsible_parties: list[dict[str, str]]
    recommended_refund_brl: float
    resolution_actions: list[str]
    notes: list[str]


def payments_match_items(bundle: OrderBundle) -> bool:
    if not bundle.items:
        # No item rows: cannot compare item+freight; treat as matched for claim checks.
        return True
    return abs(bundle.payment_total_brl - bundle.expected_total_brl) <= PAYMENT_MATCH_TOLERANCE_BRL


def is_delivery_late(bundle: OrderBundle) -> bool:
    delivered = _to_ts(bundle.order.get("order_delivered_customer_date"))
    estimated = _to_ts(bundle.order.get("order_estimated_delivery_date"))
    if delivered is None or estimated is None:
        return False
    return delivered > estimated


def seller_handoff_late(bundle: OrderBundle) -> tuple[bool, str | None]:
    """Seller late if carrier receive date > shipping_limit of that seller's item."""
    carrier = _to_ts(bundle.order.get("order_delivered_carrier_date"))
    if carrier is None or not bundle.items:
        return False, None
    for item in bundle.items:
        limit = _to_ts(item.get("shipping_limit_date"))
        if limit is not None and carrier > limit:
            return True, str(item.get("seller_id") or "")
    return False, None


def apply_policy(bundle: OrderBundle) -> PolicyDecision:
    notes: list[str] = []
    status = bundle.order_status
    pay_total = bundle.payment_total_brl
    freight = bundle.freight_total_brl

    # Priority 1
    if status == "canceled" and pay_total > 0:
        return PolicyDecision(
            primary_issue="canceled_order_paid",
            case_status="action_required",
            confidence=0.98,
            cause_code="ORDER_CANCELED_AFTER_PAYMENT",
            responsible_parties=[{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
            recommended_refund_brl=pay_total,
            resolution_actions=["issue_full_refund"],
            notes=["canceled with positive payment total"],
        )

    # Priority 2
    if status == "unavailable" and pay_total > 0:
        return PolicyDecision(
            primary_issue="unavailable_order_paid",
            case_status="action_required",
            confidence=0.98,
            cause_code="ORDER_UNAVAILABLE_AFTER_PAYMENT",
            responsible_parties=[{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
            recommended_refund_brl=pay_total,
            resolution_actions=["issue_full_refund"],
            notes=["unavailable with positive payment total"],
        )

    late = is_delivery_late(bundle)
    seller_late, late_seller_id = seller_handoff_late(bundle)

    # Priority 3
    if late and seller_late:
        parties = []
        if late_seller_id:
            parties.append({"party_type": "seller", "party_id": late_seller_id})
        return PolicyDecision(
            primary_issue="late_delivery_seller",
            case_status="action_required",
            confidence=0.95,
            cause_code="SELLER_HANDOFF_AFTER_LIMIT",
            responsible_parties=parties,
            recommended_refund_brl=freight,
            resolution_actions=["refund_freight"],
            notes=["customer delivery after estimate; carrier after shipping_limit"],
        )

    # Priority 4
    if late and not seller_late:
        return PolicyDecision(
            primary_issue="late_delivery_logistics",
            case_status="action_required",
            confidence=0.94,
            cause_code="CARRIER_DELIVERED_AFTER_ESTIMATE",
            responsible_parties=[
                {"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}
            ],
            recommended_refund_brl=freight,
            resolution_actions=["refund_freight"],
            notes=["customer delivery after estimate; seller handoff on time"],
        )

    # Priority 5
    if len(bundle.payments) >= 2 and payments_match_items(bundle):
        return PolicyDecision(
            primary_issue="valid_split_payment",
            case_status="no_action",
            confidence=0.93,
            cause_code="MULTIPLE_PAYMENTS_RECONCILED",
            responsible_parties=[],
            recommended_refund_brl=0.0,
            resolution_actions=["explain_valid_split_payment"],
            notes=["split payments reconcile with item+freight within tolerance"],
        )

    # Priority 6
    if (not late) and payments_match_items(bundle):
        return PolicyDecision(
            primary_issue="unsupported_late_claim",
            case_status="no_action",
            confidence=0.92,
            cause_code="DELIVERY_WITHIN_ESTIMATE",
            responsible_parties=[],
            recommended_refund_brl=0.0,
            resolution_actions=["reject_late_refund"],
            notes=["delivery within estimate and payments match"],
        )

    # Fallback: still produce a schema-valid conservative decision
    notes.append("fallback: no high-priority rule matched exactly")
    if late:
        return PolicyDecision(
            primary_issue="late_delivery_logistics",
            case_status="action_required",
            confidence=0.70,
            cause_code="CARRIER_DELIVERED_AFTER_ESTIMATE",
            responsible_parties=[
                {"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}
            ],
            recommended_refund_brl=freight,
            resolution_actions=["refund_freight"],
            notes=notes,
        )

    return PolicyDecision(
        primary_issue="unsupported_late_claim",
        case_status="no_action",
        confidence=0.75,
        cause_code="DELIVERY_WITHIN_ESTIMATE",
        responsible_parties=[],
        recommended_refund_brl=0.0,
        resolution_actions=["reject_late_refund"],
        notes=notes,
    )
