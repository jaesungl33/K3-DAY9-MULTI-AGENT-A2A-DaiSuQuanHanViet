"""Policy Agent — apply EC_POLICY_V1 priority rules."""

from __future__ import annotations

from src.agents.base import A2AMessage, BaseAgent
from src.data.evidence import build_evidence_ids
from src.data.policy import apply_policy
from src.data.store import DataStore


class PolicyAgent(BaseAgent):
    name = "policy_agent"
    role = "Apply EC_POLICY_V1 priority rules to produce refund and actions"
    data_access = ["policy:EC_POLICY_V1"]

    def __init__(self, store: DataStore):
        self.store = store

    def handle(self, message: A2AMessage) -> A2AMessage:
        order_id = message.payload["order_id"]
        bundle = self.store.get_order_bundle(order_id)
        assert bundle is not None

        decision = apply_policy(bundle)
        evidence = build_evidence_ids(bundle, decision)

        draft = {
            "case_id": message.case_id,
            "assessment": {
                "primary_issue": decision.primary_issue,
                "case_status": decision.case_status,
                "confidence": decision.confidence,
            },
            "affected_entities": {
                "order_ids": [order_id],
                # Keep all related entities from the order (needed for Entity score).
                "item_ids": message.payload.get("item_ids", [])[:5],
                "seller_ids": message.payload.get("seller_ids", [])[:5],
                "payment_ids": message.payload.get("payment_ids", [])[:5],
            },
            "root_cause_analysis": {
                "ranked_causes": [{"cause_code": decision.cause_code, "rank": 1}],
                "responsible_parties": decision.responsible_parties[:3],
            },
            "evidence_ids": evidence,
            "financial_resolution": {
                "currency": "BRL",
                "item_total_brl": bundle.item_total_brl,
                "freight_total_brl": bundle.freight_total_brl,
                "payment_total_brl": bundle.payment_total_brl,
                "recommended_refund_brl": decision.recommended_refund_brl,
            },
            "resolution_actions": decision.resolution_actions[:5],
        }

        return self.handoff(
            to_agent="verifier_agent",
            case_id=message.case_id,
            intent="policy_decision",
            payload={
                "draft_output": draft,
                "policy_notes": decision.notes,
                "upstream": {
                    "order_status": message.payload.get("order_status"),
                    "delivery": message.payload.get("delivery"),
                    "payment_match": message.payload.get("payment_match"),
                    "split_payment": message.payload.get("split_payment"),
                },
            },
            evidence_ids=evidence,
        )
