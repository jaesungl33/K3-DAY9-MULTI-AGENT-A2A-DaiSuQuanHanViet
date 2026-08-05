"""Order and seller domain analysis."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.agents.base import BaseAgent
from src.data_loader import get_order, get_order_items, parse_ts
from src.models import OrderSellerReport
from src.prompts import ORDER_SELLER_SYSTEM


class OrderSellerAgent(BaseAgent):
    name = "order_seller_agent"

    def run(self, case_id: str, context: dict[str, Any]) -> dict[str, Any]:
        order_id = context["claimed_order_id"]
        customer_message = context.get("customer_message", "")
        order = get_order(order_id)
        items = get_order_items(order_id)
        seller_ids = list(dict.fromkeys(item.seller_id for item in items))

        seller_late = False
        violating_seller_id: str | None = None
        carrier_ts = parse_ts(order.order_delivered_carrier_date) if order else None

        for item in items:
            limit_ts = parse_ts(item.shipping_limit_date)
            if carrier_ts is not None and limit_ts is not None and carrier_ts > limit_ts:
                seller_late = True
                violating_seller_id = item.seller_id
                break

        evidence_ids: list[str] = []
        if order:
            evidence_ids.append(f"order:{order_id}")
        for item in items[:3]:
            evidence_ids.append(f"item:{order_id}:{item.order_item_id}")
        for seller_id in seller_ids[:2]:
            evidence_ids.append(f"seller:{seller_id}")

        facts = {
            "order_id": order_id,
            "customer_message": customer_message,
            "order": asdict(order) if order else None,
            "items": [asdict(i) for i in items],
            "seller_late_handoff": seller_late,
            "violating_seller_id": violating_seller_id,
            "computed_evidence_ids": evidence_ids,
        }
        llm_insight = self._llm_analyze(case_id, ORDER_SELLER_SYSTEM, facts)

        report = OrderSellerReport(
            order=order,
            items=items,
            seller_ids=seller_ids,
            seller_late_handoff=seller_late,
            violating_seller_id=violating_seller_id,
            evidence_ids=evidence_ids,
            llm_insight=llm_insight,
        )
        self.trace.log(case_id, "handoff", self.name, "payment_agent", report)
        return {"order_seller_report": report}
