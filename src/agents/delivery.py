"""Delivery Agent — compare actual delivery vs estimate and seller handoff."""

from __future__ import annotations

from src.agents.base import A2AMessage, BaseAgent
from src.data.policy import is_delivery_late, seller_handoff_late
from src.data.store import DataStore


class DeliveryAgent(BaseAgent):
    name = "delivery_agent"
    role = "Compare delivered_customer_date vs estimate and carrier vs shipping_limit"
    data_access = ["olist_orders_dataset", "olist_order_items_dataset"]

    def __init__(self, store: DataStore):
        self.store = store

    def handle(self, message: A2AMessage) -> A2AMessage:
        order_id = message.payload["order_id"]
        bundle = self.store.get_order_bundle(order_id)
        assert bundle is not None

        late = is_delivery_late(bundle)
        seller_late, late_seller_id = seller_handoff_late(bundle)

        payload = {
            **message.payload,
            "delivery": {
                "is_late_vs_estimate": late,
                "seller_handoff_after_limit": seller_late,
                "late_seller_id": late_seller_id,
                "carrier_date": str(bundle.order.get("order_delivered_carrier_date")),
                "customer_date": str(bundle.order.get("order_delivered_customer_date")),
                "estimated_date": str(bundle.order.get("order_estimated_delivery_date")),
            },
        }
        return self.handoff(
            to_agent="policy_agent",
            case_id=message.case_id,
            intent="delivery_findings",
            payload=payload,
            evidence_ids=message.evidence_ids,
        )
