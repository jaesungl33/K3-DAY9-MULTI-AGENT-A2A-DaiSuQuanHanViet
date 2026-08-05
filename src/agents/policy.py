"""Apply EC_POLICY_V1 business rules with LLM reasoning."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.agents.base import BaseAgent
from src.data_loader import round_brl
from src.models import (
    DeliveryReport,
    OrderRecord,
    OrderSellerReport,
    PaymentReport,
    PolicyDecision,
)
from src.prompts import POLICY_SYSTEM


class PolicyAgent(BaseAgent):
    name = "policy_agent"

    def run(self, case_id: str, context: dict[str, Any]) -> dict[str, Any]:
        order_report: OrderSellerReport = context["order_seller_report"]
        payment_report: PaymentReport = context["payment_report"]
        delivery_report: DeliveryReport = context["delivery_report"]
        order: OrderRecord | None = order_report.order

        rule_decision = self._evaluate(order, order_report, payment_report, delivery_report)

        facts = {
            "customer_message": context.get("customer_message", ""),
            "order_seller_report": {
                "seller_late_handoff": order_report.seller_late_handoff,
                "violating_seller_id": order_report.violating_seller_id,
                "order_status": order.order_status if order else None,
                "llm_summary": order_report.llm_insight.get("summary", ""),
            },
            "payment_report": {
                "payment_total_brl": payment_report.payment_total_brl,
                "payment_matches": payment_report.payment_matches,
                "has_split_payment": payment_report.has_split_payment,
                "freight_total_brl": payment_report.freight_total_brl,
                "llm_summary": payment_report.llm_insight.get("summary", ""),
            },
            "delivery_report": {
                "delivered_late": delivery_report.delivered_late,
                "carrier_on_time": delivery_report.carrier_on_time,
                "llm_summary": delivery_report.llm_insight.get("summary", ""),
            },
            "rule_engine_decision": asdict(rule_decision),
        }
        llm_insight = self._llm_analyze(case_id, POLICY_SYSTEM, facts)

        llm_confidence = llm_insight.get("confidence")
        # Keep deterministic 1.0 confidence for policy engine decisions
        rule_decision.confidence = 1.0

        rule_decision.llm_insight = llm_insight
        self.trace.log(case_id, "handoff", self.name, "verifier_agent", rule_decision)
        return {"policy_decision": rule_decision}

    def _evaluate(
        self,
        order: OrderRecord | None,
        order_report: OrderSellerReport,
        payment_report: PaymentReport,
        delivery_report: DeliveryReport,
    ) -> PolicyDecision:
        if order is None:
            return PolicyDecision(
                primary_issue="unsupported_late_claim",
                case_status="no_action",
                confidence=1.0,
                root_cause_code="DELIVERY_WITHIN_ESTIMATE",
                resolution_actions=["reject_late_refund"],
                evidence_ids=["policy:DELIVERY_WITHIN_ESTIMATE"],
            )

        status = order.order_status.lower()
        payment_total = payment_report.payment_total_brl

        if status == "canceled" and payment_total > 0:
            return self._build(
                primary_issue="canceled_order_paid",
                case_status="action_required",
                confidence=1.0,
                root_cause_code="ORDER_CANCELED_AFTER_PAYMENT",
                parties=[{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
                refund=payment_total,
                actions=["issue_full_refund"],
            )

        if status == "unavailable" and payment_total > 0:
            return self._build(
                primary_issue="unavailable_order_paid",
                case_status="action_required",
                confidence=1.0,
                root_cause_code="ORDER_UNAVAILABLE_AFTER_PAYMENT",
                parties=[{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
                refund=payment_total,
                actions=["issue_full_refund"],
            )

        if delivery_report.delivered_late and order_report.seller_late_handoff:
            seller_id = order_report.violating_seller_id or (
                order_report.seller_ids[0] if order_report.seller_ids else "UNKNOWN_SELLER"
            )
            return self._build(
                primary_issue="late_delivery_seller",
                case_status="action_required",
                confidence=1.0,
                root_cause_code="SELLER_HANDOFF_AFTER_LIMIT",
                parties=[{"party_type": "seller", "party_id": seller_id}],
                refund=payment_report.freight_total_brl,
                actions=["refund_freight"],
            )

        if delivery_report.delivered_late and delivery_report.carrier_on_time:
            return self._build(
                primary_issue="late_delivery_logistics",
                case_status="action_required",
                confidence=1.0,
                root_cause_code="CARRIER_DELIVERED_AFTER_ESTIMATE",
                parties=[{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}],
                refund=payment_report.freight_total_brl,
                actions=["refund_freight"],
            )

        if payment_report.has_split_payment and payment_report.payment_matches:
            return self._build(
                primary_issue="valid_split_payment",
                case_status="no_action",
                confidence=1.0,
                root_cause_code="MULTIPLE_PAYMENTS_RECONCILED",
                parties=[],
                refund=0.0,
                actions=["explain_valid_split_payment"],
            )

        return self._build(
            primary_issue="unsupported_late_claim",
            case_status="no_action",
            confidence=1.0,
            root_cause_code="DELIVERY_WITHIN_ESTIMATE",
            parties=[],
            refund=0.0,
            actions=["reject_late_refund"],
        )

    def _build(
        self,
        *,
        primary_issue: str,
        case_status: str,
        confidence: float,
        root_cause_code: str,
        parties: list[dict[str, str]],
        refund: float,
        actions: list[str],
    ) -> PolicyDecision:
        return PolicyDecision(
            primary_issue=primary_issue,
            case_status=case_status,
            confidence=confidence,
            root_cause_code=root_cause_code,
            responsible_parties=parties,
            recommended_refund_brl=round_brl(refund),
            resolution_actions=actions,
            evidence_ids=[f"policy:{root_cause_code}"],
        )
