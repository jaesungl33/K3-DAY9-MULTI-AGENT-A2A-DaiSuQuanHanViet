"""Coordinator Agent — receive case, dispatch specialists, assemble final output."""

from __future__ import annotations

from typing import Any

from src.agents.base import A2AMessage, BaseAgent
from src.agents.delivery import DeliveryAgent
from src.agents.order_seller import OrderSellerAgent
from src.agents.payment import PaymentAgent
from src.agents.policy_agent import PolicyAgent
from src.agents.verifier import VerifierAgent
from src.data.store import DataStore


class CoordinatorAgent(BaseAgent):
    name = "coordinator"
    role = "Orchestrate specialist agents via A2A handoffs and emit final output"
    data_access = ["input_case"]

    def __init__(self, store: DataStore):
        self.store = store
        self.order_seller = OrderSellerAgent(store)
        self.payment = PaymentAgent(store)
        self.delivery = DeliveryAgent(store)
        self.policy = PolicyAgent(store)
        self.verifier = VerifierAgent()
        self.route = {
            "order_seller_agent": self.order_seller,
            "payment_agent": self.payment,
            "delivery_agent": self.delivery,
            "policy_agent": self.policy,
            "verifier_agent": self.verifier,
        }

    def resolve_case(self, case: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        case_id = case["case_id"]
        order_id = case["customer_request"]["claimed_order_id"]
        trace: list[dict[str, Any]] = []

        msg = self.handoff(
            to_agent="order_seller_agent",
            case_id=case_id,
            intent="investigate_case",
            payload={
                "order_id": order_id,
                "opened_at": case.get("opened_at"),
                "customer_message": case.get("customer_request", {}).get("message"),
                "policy_version": case.get("policy_version", "EC_POLICY_V1"),
            },
        )
        trace.append(msg.to_dict())

        # Follow handoff chain until message returns to coordinator
        hops = 0
        while msg.to_agent != "coordinator" and hops < 16:
            agent = self.route.get(msg.to_agent)
            if agent is None:
                raise RuntimeError(f"Unknown agent route: {msg.to_agent}")
            msg = agent.handle(msg)
            trace.append(msg.to_dict())
            hops += 1

        if msg.intent == "order_not_found":
            output = self._empty_not_found(case_id, order_id)
            return output, trace

        if msg.intent != "verified_output":
            raise RuntimeError(f"Unexpected terminal intent: {msg.intent}")

        return msg.payload["output"], trace

    def _empty_not_found(self, case_id: str, order_id: str) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "assessment": {
                "primary_issue": "unsupported_late_claim",
                "case_status": "no_action",
                "confidence": 0.5,
            },
            "affected_entities": {
                "order_ids": [order_id],
                "item_ids": [],
                "seller_ids": [],
                "payment_ids": [],
            },
            "root_cause_analysis": {
                "ranked_causes": [{"cause_code": "DELIVERY_WITHIN_ESTIMATE", "rank": 1}],
                "responsible_parties": [],
            },
            "evidence_ids": [f"order:{order_id}", "policy:DELIVERY_WITHIN_ESTIMATE"],
            "financial_resolution": {
                "currency": "BRL",
                "item_total_brl": 0.0,
                "freight_total_brl": 0.0,
                "payment_total_brl": 0.0,
                "recommended_refund_brl": 0.0,
            },
            "resolution_actions": ["reject_late_refund"],
        }
