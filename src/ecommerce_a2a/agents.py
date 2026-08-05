from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .models import (
    DeliveryFinding,
    OrderSellerFinding,
    PaymentFinding,
    PolicyDecision,
)
from .repository import OlistRepository


CENT = Decimal("0.01")
PAYMENT_TOLERANCE = Decimal("0.10")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


class OrderSellerAgent:
    name = "order_seller_agent"

    def __init__(self, repository: OlistRepository):
        self.repository = repository

    def investigate(self, order_id: str) -> OrderSellerFinding:
        order = self.repository.get_order(order_id)
        items = self.repository.get_items(order_id)
        seller_ids = tuple(dict.fromkeys(item.seller_id for item in items))
        return OrderSellerFinding(
            order=order,
            items=items,
            seller_ids=seller_ids,
            item_total=money(sum((item.price for item in items), Decimal("0"))),
            freight_total=money(sum((item.freight_value for item in items), Decimal("0"))),
        )


class PaymentAgent:
    name = "payment_agent"

    def __init__(self, repository: OlistRepository):
        self.repository = repository

    def reconcile(self, order_id: str, order_finding: OrderSellerFinding) -> PaymentFinding:
        payments = self.repository.get_payments(order_id)
        payment_total = money(sum((payment.payment_value for payment in payments), Decimal("0")))
        order_total = money(order_finding.item_total + order_finding.freight_total)
        matches = abs(payment_total - order_total) <= PAYMENT_TOLERANCE
        return PaymentFinding(
            payments=payments,
            payment_total=payment_total,
            payment_matches_order_total=matches,
            is_split_payment=len(payments) >= 2,
        )


class DeliveryAgent:
    name = "delivery_agent"

    def analyze(self, order_finding: OrderSellerFinding) -> DeliveryFinding:
        order = order_finding.order
        delivered_late = bool(
            order.delivered_customer_at
            and order.estimated_delivery_at
            and order.delivered_customer_at > order.estimated_delivery_at
        )
        delivered_within_estimate = bool(
            order.delivered_customer_at
            and order.estimated_delivery_at
            and order.delivered_customer_at <= order.estimated_delivery_at
        )

        offending_items = []
        if order.delivered_carrier_at:
            offending_items = [
                item
                for item in order_finding.items
                if item.shipping_limit_at and order.delivered_carrier_at > item.shipping_limit_at
            ]

        offending_sellers = tuple(dict.fromkeys(item.seller_id for item in offending_items))
        offending_item_ids = tuple(
            f"{item.order_id}:{item.order_item_id}" for item in offending_items
        )
        return DeliveryFinding(
            delivered_late=delivered_late,
            delivered_within_estimate=delivered_within_estimate,
            seller_handoff_late=delivered_late and bool(offending_items),
            offending_seller_ids=offending_sellers,
            offending_item_ids=offending_item_ids,
        )


class PolicyAgent:
    name = "policy_agent"

    def decide(
        self,
        order_finding: OrderSellerFinding,
        payment_finding: PaymentFinding,
        delivery_finding: DeliveryFinding,
    ) -> PolicyDecision:
        status = order_finding.order.order_status
        payment_total = payment_finding.payment_total

        if status == "canceled" and payment_total > 0:
            return PolicyDecision(
                primary_issue="canceled_order_paid",
                case_status="action_required",
                confidence=0.99,
                cause_code="ORDER_CANCELED_AFTER_PAYMENT",
                responsible_parties=({"party_type": "platform", "party_id": "OLIST_PLATFORM"},),
                recommended_refund=payment_total,
                resolution_actions=("issue_full_refund",),
            )

        if status == "unavailable" and payment_total > 0:
            return PolicyDecision(
                primary_issue="unavailable_order_paid",
                case_status="action_required",
                confidence=0.99,
                cause_code="ORDER_UNAVAILABLE_AFTER_PAYMENT",
                responsible_parties=({"party_type": "platform", "party_id": "OLIST_PLATFORM"},),
                recommended_refund=payment_total,
                resolution_actions=("issue_full_refund",),
            )

        if delivery_finding.seller_handoff_late:
            parties = tuple(
                {"party_type": "seller", "party_id": seller_id}
                for seller_id in delivery_finding.offending_seller_ids[:3]
            )
            return PolicyDecision(
                primary_issue="late_delivery_seller",
                case_status="action_required",
                confidence=0.98,
                cause_code="SELLER_HANDOFF_AFTER_LIMIT",
                responsible_parties=parties,
                recommended_refund=order_finding.freight_total,
                resolution_actions=("refund_freight",),
            )

        if delivery_finding.delivered_late:
            return PolicyDecision(
                primary_issue="late_delivery_logistics",
                case_status="action_required",
                confidence=0.98,
                cause_code="CARRIER_DELIVERED_AFTER_ESTIMATE",
                responsible_parties=(
                    {"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"},
                ),
                recommended_refund=order_finding.freight_total,
                resolution_actions=("refund_freight",),
            )

        if payment_finding.is_split_payment and payment_finding.payment_matches_order_total:
            return PolicyDecision(
                primary_issue="valid_split_payment",
                case_status="no_action",
                confidence=0.99,
                cause_code="MULTIPLE_PAYMENTS_RECONCILED",
                responsible_parties=(),
                recommended_refund=Decimal("0.00"),
                resolution_actions=("explain_valid_split_payment",),
            )

        if delivery_finding.delivered_within_estimate and payment_finding.payment_matches_order_total:
            return PolicyDecision(
                primary_issue="unsupported_late_claim",
                case_status="no_action",
                confidence=0.98,
                cause_code="DELIVERY_WITHIN_ESTIMATE",
                responsible_parties=(),
                recommended_refund=Decimal("0.00"),
                resolution_actions=("reject_late_refund",),
            )

        raise ValueError(
            "Case does not match any EC_POLICY_V1 rule. "
            f"order_id={order_finding.order.order_id}, status={status}, "
            f"delivered_late={delivery_finding.delivered_late}, "
            f"payment_match={payment_finding.payment_matches_order_total}, "
            f"payment_rows={len(payment_finding.payments)}"
        )


class VerifierAgent:
    name = "verifier_agent"

    REQUIRED_TOP_LEVEL = {
        "case_id",
        "assessment",
        "affected_entities",
        "root_cause_analysis",
        "evidence_ids",
        "financial_resolution",
        "resolution_actions",
    }

    def __init__(self, repository: OlistRepository):
        self.repository = repository

    def verify(self, output: dict[str, Any], case_id: str, order_id: str) -> None:
        if set(output) != self.REQUIRED_TOP_LEVEL:
            raise ValueError(f"Output top-level schema mismatch: {sorted(output)}")
        if output["case_id"] != case_id:
            raise ValueError("case_id mismatch")
        if output["affected_entities"]["order_ids"] != [order_id]:
            raise ValueError("affected order_id mismatch")
        confidence = output["assessment"]["confidence"]
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be in [0, 1]")
        if len(output["evidence_ids"]) > 10:
            raise ValueError("Too many evidence IDs")
        if any(len(output["affected_entities"][key]) > 5 for key in (
            "order_ids", "item_ids", "seller_ids", "payment_ids"
        )):
            raise ValueError("Too many affected entity IDs")
        if len(output["root_cause_analysis"]["ranked_causes"]) > 3:
            raise ValueError("Too many root causes")
        if len(output["root_cause_analysis"]["responsible_parties"]) > 3:
            raise ValueError("Too many responsible parties")
        if len(output["resolution_actions"]) > 5:
            raise ValueError("Too many actions")

        items = self.repository.get_items(order_id)
        payments = self.repository.get_payments(order_id)
        valid_item_ids = {f"{item.order_id}:{item.order_item_id}" for item in items}
        valid_payment_ids = {f"{payment.order_id}:{payment.payment_sequential}" for payment in payments}
        valid_seller_ids = {item.seller_id for item in items}

        entities = output["affected_entities"]
        if not set(entities["item_ids"]).issubset(valid_item_ids):
            raise ValueError("Invalid affected item ID")
        if not set(entities["payment_ids"]).issubset(valid_payment_ids):
            raise ValueError("Invalid affected payment ID")
        if not set(entities["seller_ids"]).issubset(valid_seller_ids):
            raise ValueError("Invalid affected seller ID")

        valid_evidence = {f"order:{order_id}"}
        valid_evidence |= {f"item:{value}" for value in valid_item_ids}
        valid_evidence |= {f"payment:{value}" for value in valid_payment_ids}
        valid_evidence |= {f"seller:{value}" for value in valid_seller_ids}
        valid_evidence.add(
            "policy:" + output["root_cause_analysis"]["ranked_causes"][0]["cause_code"]
        )
        if not set(output["evidence_ids"]).issubset(valid_evidence):
            raise ValueError("Evidence contains an ID not supported by CSV/policy")
