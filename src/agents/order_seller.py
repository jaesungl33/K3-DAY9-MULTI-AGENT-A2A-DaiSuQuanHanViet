"""Order & Seller Agent — status, items, sellers, shipping limits."""

from __future__ import annotations

from src.agents.base import A2AMessage, BaseAgent
from src.data.store import DataStore


class OrderSellerAgent(BaseAgent):
    name = "order_seller_agent"
    role = "Inspect order status, line items, sellers, and shipping_limit_date"
    data_access = ["olist_orders_dataset", "olist_order_items_dataset", "olist_sellers_dataset"]

    def __init__(self, store: DataStore):
        self.store = store

    def handle(self, message: A2AMessage) -> A2AMessage:
        order_id = message.payload["order_id"]
        bundle = self.store.get_order_bundle(order_id)
        if bundle is None:
            return self.handoff(
                to_agent="coordinator",
                case_id=message.case_id,
                intent="order_not_found",
                payload={"order_id": order_id, "error": "order_id not found in Olist"},
            )

        evidence = [f"order:{order_id}"]
        item_ids = []
        seller_ids = []
        for item in bundle.items:
            iid = f"{order_id}:{item['order_item_id']}"
            item_ids.append(iid)
            evidence.append(f"item:{order_id}:{item['order_item_id']}")
            sid = item.get("seller_id")
            if sid and sid not in seller_ids:
                seller_ids.append(sid)
                evidence.append(f"seller:{sid}")

        payload = {
            "order_id": order_id,
            "order_status": bundle.order_status,
            "timestamps": {
                "purchase": str(bundle.order.get("order_purchase_timestamp")),
                "approved": str(bundle.order.get("order_approved_at")),
                "carrier": str(bundle.order.get("order_delivered_carrier_date")),
                "customer": str(bundle.order.get("order_delivered_customer_date")),
                "estimated": str(bundle.order.get("order_estimated_delivery_date")),
            },
            "items": [
                {
                    "order_item_id": int(i["order_item_id"]),
                    "seller_id": i.get("seller_id"),
                    "price": float(i.get("price") or 0),
                    "freight_value": float(i.get("freight_value") or 0),
                    "shipping_limit_date": str(i.get("shipping_limit_date")),
                }
                for i in bundle.items
            ],
            "item_ids": item_ids,
            "seller_ids": seller_ids,
            "item_total_brl": bundle.item_total_brl,
            "freight_total_brl": bundle.freight_total_brl,
        }
        return self.handoff(
            to_agent="payment_agent",
            case_id=message.case_id,
            intent="order_seller_findings",
            payload=payload,
            evidence_ids=evidence,
        )
