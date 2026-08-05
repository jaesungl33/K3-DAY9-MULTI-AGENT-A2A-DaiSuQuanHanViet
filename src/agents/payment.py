"""Payment reconciliation agent."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.agents.base import BaseAgent
from src.data_loader import get_payments, round_brl
from src.models import OrderItemRecord, PaymentReport
from src.prompts import PAYMENT_SYSTEM


class PaymentAgent(BaseAgent):
    name = "payment_agent"

    def run(self, case_id: str, context: dict[str, Any]) -> dict[str, Any]:
        order_id = context["claimed_order_id"]
        items: list[OrderItemRecord] = context["order_seller_report"].items
        payments = get_payments(order_id)

        item_total = round_brl(sum(item.price for item in items))
        freight_total = round_brl(sum(item.freight_value for item in items))
        expected_total = round_brl(item_total + freight_total)
        payment_total = round_brl(sum(p.payment_value for p in payments))
        payment_matches = abs(payment_total - expected_total) <= 0.10

        evidence_ids = [f"payment:{order_id}:{p.payment_sequential}" for p in payments[:3]]

        facts = {
            "order_id": order_id,
            "payments": [asdict(p) for p in payments],
            "item_total_brl": item_total,
            "freight_total_brl": freight_total,
            "expected_total_brl": expected_total,
            "payment_total_brl": payment_total,
            "payment_matches": payment_matches,
            "has_split_payment": len(payments) >= 2,
            "prior_handoff": context["order_seller_report"].llm_insight.get("summary", ""),
            "computed_evidence_ids": evidence_ids,
        }
        llm_insight = self._llm_analyze(case_id, PAYMENT_SYSTEM, facts)

        report = PaymentReport(
            payments=payments,
            payment_total_brl=payment_total,
            item_total_brl=item_total,
            freight_total_brl=freight_total,
            expected_total_brl=expected_total,
            payment_matches=payment_matches,
            has_split_payment=len(payments) >= 2,
            evidence_ids=evidence_ids,
            llm_insight=llm_insight,
        )
        self.trace.log(case_id, "handoff", self.name, "delivery_agent", report)
        return {"payment_report": report}
