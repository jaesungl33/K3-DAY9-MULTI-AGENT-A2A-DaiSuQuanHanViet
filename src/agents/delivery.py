"""Delivery timeline analysis agent."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.agents.base import BaseAgent
from src.data_loader import parse_ts
from src.models import DeliveryReport, OrderRecord
from src.prompts import DELIVERY_SYSTEM


class DeliveryAgent(BaseAgent):
    name = "delivery_agent"

    def run(self, case_id: str, context: dict[str, Any]) -> dict[str, Any]:
        order: OrderRecord | None = context["order_seller_report"].order
        order_id = context["claimed_order_id"]
        seller_late = context["order_seller_report"].seller_late_handoff

        delivered_late = False
        carrier_after_limit = seller_late
        carrier_on_time = not seller_late

        if order:
            actual = parse_ts(order.order_delivered_customer_date)
            estimated = parse_ts(order.order_estimated_delivery_date)
            if actual is not None and estimated is not None:
                delivered_late = actual > estimated

        evidence_ids: list[str] = []
        if order:
            evidence_ids.append(f"order:{order_id}")

        facts = {
            "order_id": order_id,
            "order": asdict(order) if order else None,
            "delivered_late": delivered_late,
            "seller_late_handoff": seller_late,
            "carrier_on_time": carrier_on_time,
            "estimated_delivery_date": order.order_estimated_delivery_date if order else None,
            "actual_delivery_date": order.order_delivered_customer_date if order else None,
            "carrier_handoff_date": order.order_delivered_carrier_date if order else None,
            "prior_handoff": {
                "order_seller": context["order_seller_report"].llm_insight.get("summary", ""),
                "payment": context["payment_report"].llm_insight.get("summary", ""),
            },
            "computed_evidence_ids": evidence_ids,
        }
        llm_insight = self._llm_analyze(case_id, DELIVERY_SYSTEM, facts)

        report = DeliveryReport(
            delivered_late=delivered_late,
            carrier_after_limit=carrier_after_limit,
            carrier_on_time=carrier_on_time,
            estimated_delivery_date=order.order_estimated_delivery_date if order else None,
            actual_delivery_date=order.order_delivered_customer_date if order else None,
            carrier_handoff_date=order.order_delivered_carrier_date if order else None,
            evidence_ids=evidence_ids,
            llm_insight=llm_insight,
        )
        self.trace.log(case_id, "handoff", self.name, "policy_agent", report)
        return {"delivery_report": report}
