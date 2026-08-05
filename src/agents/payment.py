"""Payment Agent — reconcile payment rows vs item+freight."""

from __future__ import annotations

from src.agents.base import A2AMessage, BaseAgent
from src.config import PAYMENT_MATCH_TOLERANCE_BRL
from src.data.policy import payments_match_items
from src.data.store import DataStore


class PaymentAgent(BaseAgent):
    name = "payment_agent"
    role = "Reconcile payment rows against item price + freight totals"
    data_access = ["olist_order_payments_dataset"]

    def __init__(self, store: DataStore):
        self.store = store

    def handle(self, message: A2AMessage) -> A2AMessage:
        order_id = message.payload["order_id"]
        bundle = self.store.get_order_bundle(order_id)
        assert bundle is not None

        payment_ids = [
            f"{order_id}:{p['payment_sequential']}" for p in bundle.payments
        ]
        evidence = [f"payment:{order_id}:{p['payment_sequential']}" for p in bundle.payments]

        matched = payments_match_items(bundle)
        payload = {
            **message.payload,
            "payments": [
                {
                    "payment_sequential": int(p["payment_sequential"]),
                    "payment_type": p.get("payment_type"),
                    "payment_installments": p.get("payment_installments"),
                    "payment_value": float(p.get("payment_value") or 0),
                }
                for p in bundle.payments
            ],
            "payment_ids": payment_ids,
            "payment_total_brl": bundle.payment_total_brl,
            "expected_total_brl": bundle.expected_total_brl,
            "payment_match": matched,
            "payment_delta_brl": round(
                abs(bundle.payment_total_brl - bundle.expected_total_brl), 2
            ),
            "tolerance_brl": PAYMENT_MATCH_TOLERANCE_BRL,
            "split_payment": len(bundle.payments) >= 2,
        }
        return self.handoff(
            to_agent="delivery_agent",
            case_id=message.case_id,
            intent="payment_findings",
            payload=payload,
            evidence_ids=list(dict.fromkeys(message.evidence_ids + evidence)),
        )
