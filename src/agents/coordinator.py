"""Coordinator orchestrates multi-agent handoffs for each case."""

from __future__ import annotations

from typing import Any

from src.agents.base import BaseAgent, TraceLogger
from src.agents.delivery import DeliveryAgent
from src.agents.order_seller import OrderSellerAgent
from src.agents.payment import PaymentAgent
from src.agents.policy import PolicyAgent
from src.agents.verifier import VerifierAgent
from src.llm_client import LLMClient
from src.models import (
    CaseInput,
    CaseOutput,
    DeliveryReport,
    OrderSellerReport,
    PaymentReport,
    PolicyDecision,
)
from src.prompts import COORDINATOR_SYSTEM


class CoordinatorAgent(BaseAgent):
    name = "coordinator_agent"

    def __init__(self, trace: TraceLogger, llm: LLMClient) -> None:
        super().__init__(trace, llm)
        self.order_seller = OrderSellerAgent(trace, llm)
        self.payment = PaymentAgent(trace, llm)
        self.delivery = DeliveryAgent(trace, llm)
        self.policy = PolicyAgent(trace, llm)
        self.verifier = VerifierAgent(trace, llm)

    def run(self, case_id: str, context: dict[str, Any]) -> dict[str, Any]:
        case: CaseInput = context["case_input"]
        self.trace.log(case_id, "case_start", self.name, self.order_seller.name, case)

        ctx: dict[str, Any] = {
            "claimed_order_id": case.claimed_order_id,
            "customer_message": case.customer_message,
        }
        ctx.update(self.order_seller.run(case_id, ctx))
        ctx.update(self.payment.run(case_id, ctx))
        ctx.update(self.delivery.run(case_id, ctx))
        ctx.update(self.policy.run(case_id, ctx))

        draft_output = self._compose_output(case, ctx)
        ctx["draft_output"] = draft_output
        verification = self.verifier.run(case_id, ctx)

        final_output = verification["verified_output"]
        synthesis = self._llm_analyze(
            case_id,
            COORDINATOR_SYSTEM,
            {
                "case_id": case.case_id,
                "customer_message": case.customer_message,
                "final_output": final_output,
                "agent_summaries": {
                    "order_seller": ctx["order_seller_report"].llm_insight.get("summary", ""),
                    "payment": ctx["payment_report"].llm_insight.get("summary", ""),
                    "delivery": ctx["delivery_report"].llm_insight.get("summary", ""),
                    "policy": ctx["policy_decision"].llm_insight.get("summary", ""),
                },
            },
        )
        self.trace.log(case_id, "case_complete", self.name, None, {"output": final_output, "synthesis": synthesis})
        return {"case_output": CaseOutput(case_id=case.case_id, payload=final_output)}

    def _compose_output(self, case: CaseInput, ctx: dict[str, Any]) -> dict[str, Any]:
        order_report: OrderSellerReport = ctx["order_seller_report"]
        payment_report: PaymentReport = ctx["payment_report"]
        delivery_report: DeliveryReport = ctx["delivery_report"]
        decision: PolicyDecision = ctx["policy_decision"]

        order_id = case.claimed_order_id
        order = order_report.order

        item_ids = [f"{item.order_id}:{item.order_item_id}" for item in order_report.items[:5]]
        seller_ids = order_report.seller_ids[:5]
        payment_ids = [
            f"{payment.order_id}:{payment.payment_sequential}" for payment in payment_report.payments[:5]
        ]

        evidence_ids: list[str] = []
        if order:
            evidence_ids.append(f"order:{order_id}")

        issue = decision.primary_issue
        if issue in ("canceled_order_paid", "unavailable_order_paid"):
            for payment in payment_report.payments[:5]:
                ev = f"payment:{payment.order_id}:{payment.payment_sequential}"
                if ev not in evidence_ids:
                    evidence_ids.append(ev)
        elif issue == "late_delivery_seller":
            for item in order_report.items[:5]:
                ev = f"item:{order_id}:{item.order_item_id}"
                if ev not in evidence_ids:
                    evidence_ids.append(ev)
            for payment in payment_report.payments[:5]:
                ev = f"payment:{payment.order_id}:{payment.payment_sequential}"
                if ev not in evidence_ids:
                    evidence_ids.append(ev)
            if order_report.violating_seller_id:
                ev = f"seller:{order_report.violating_seller_id}"
                if ev not in evidence_ids:
                    evidence_ids.append(ev)
            else:
                for seller_id in seller_ids[:5]:
                    ev = f"seller:{seller_id}"
                    if ev not in evidence_ids:
                        evidence_ids.append(ev)
        elif issue == "late_delivery_logistics":
            for item in order_report.items[:5]:
                ev = f"item:{order_id}:{item.order_item_id}"
                if ev not in evidence_ids:
                    evidence_ids.append(ev)
            for payment in payment_report.payments[:5]:
                ev = f"payment:{payment.order_id}:{payment.payment_sequential}"
                if ev not in evidence_ids:
                    evidence_ids.append(ev)
        elif issue == "valid_split_payment":
            for payment in payment_report.payments[:5]:
                ev = f"payment:{payment.order_id}:{payment.payment_sequential}"
                if ev not in evidence_ids:
                    evidence_ids.append(ev)
        elif issue == "unsupported_late_claim":
            pass

        policy_ev = f"policy:{decision.root_cause_code}"
        if policy_ev not in evidence_ids:
            evidence_ids.append(policy_ev)

        return {
            "assessment": {
                "primary_issue": decision.primary_issue,
                "case_status": decision.case_status,
                "confidence": decision.confidence,
            },
            "affected_entities": {
                "order_ids": [order_id] if order else [],
                "item_ids": item_ids,
                "seller_ids": seller_ids,
                "payment_ids": payment_ids,
            },
            "root_cause_analysis": {
                "ranked_causes": [{"cause_code": decision.root_cause_code, "rank": 1}],
                "responsible_parties": decision.responsible_parties[:3],
            },
            "evidence_ids": evidence_ids[:10],
            "financial_resolution": {
                "currency": "BRL",
                "item_total_brl": payment_report.item_total_brl,
                "freight_total_brl": payment_report.freight_total_brl,
                "payment_total_brl": payment_report.payment_total_brl,
                "recommended_refund_brl": decision.recommended_refund_brl,
            },
            "resolution_actions": decision.resolution_actions[:5],
        }
