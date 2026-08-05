"""Verifier Agent — schema, limits, evidence format, money rounding."""

from __future__ import annotations

from src.agents.base import A2AMessage, BaseAgent
from src.config import (
    MAX_ACTIONS,
    MAX_ENTITY_IDS,
    MAX_EVIDENCE_IDS,
    MAX_RESPONSIBLE_PARTIES,
    MAX_ROOT_CAUSES,
    MONEY_ROUND,
)

VALID_ISSUES = {
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
}
VALID_STATUS = {"action_required", "no_action"}
VALID_ACTIONS = {
    "issue_full_refund",
    "refund_freight",
    "explain_valid_split_payment",
    "reject_late_refund",
}


def _cap(values: list, n: int) -> list:
    return list(values)[:n]


def _round_money_fields(fin: dict) -> dict:
    out = dict(fin)
    for key in (
        "item_total_brl",
        "freight_total_brl",
        "payment_total_brl",
        "recommended_refund_brl",
    ):
        if key in out:
            out[key] = round(float(out[key]), MONEY_ROUND)
    return out


def _valid_evidence(eid: str) -> bool:
    parts = eid.split(":")
    if len(parts) < 2:
        return False
    kind = parts[0]
    if kind == "order" and len(parts) == 2:
        return bool(parts[1])
    if kind == "item" and len(parts) == 3:
        return bool(parts[1]) and parts[2].isdigit()
    if kind == "payment" and len(parts) == 3:
        return bool(parts[1]) and parts[2].isdigit()
    if kind == "seller" and len(parts) == 2:
        return bool(parts[1])
    if kind == "policy" and len(parts) == 2:
        return bool(parts[1])
    return False


class VerifierAgent(BaseAgent):
    name = "verifier_agent"
    role = "Validate schema limits, evidence IDs, and financial rounding before write"
    data_access = []

    def handle(self, message: A2AMessage) -> A2AMessage:
        draft = message.payload["draft_output"]
        issues: list[str] = []

        assessment = draft["assessment"]
        if assessment["primary_issue"] not in VALID_ISSUES:
            issues.append(f"invalid primary_issue: {assessment['primary_issue']}")
        if assessment["case_status"] not in VALID_STATUS:
            issues.append(f"invalid case_status: {assessment['case_status']}")
        conf = float(assessment["confidence"])
        assessment["confidence"] = max(0.0, min(1.0, conf))

        entities = draft["affected_entities"]
        for key in ("order_ids", "item_ids", "seller_ids", "payment_ids"):
            entities[key] = _cap(entities.get(key, []), MAX_ENTITY_IDS)

        rca = draft["root_cause_analysis"]
        rca["ranked_causes"] = _cap(rca.get("ranked_causes", []), MAX_ROOT_CAUSES)
        rca["responsible_parties"] = _cap(
            rca.get("responsible_parties", []), MAX_RESPONSIBLE_PARTIES
        )

        evidence = [e for e in draft.get("evidence_ids", []) if _valid_evidence(e)]
        # de-dupe preserve order
        seen = set()
        unique_evidence = []
        for e in evidence:
            if e not in seen:
                seen.add(e)
                unique_evidence.append(e)
        draft["evidence_ids"] = unique_evidence[:MAX_EVIDENCE_IDS]

        draft["financial_resolution"] = _round_money_fields(draft["financial_resolution"])
        actions = [a for a in draft.get("resolution_actions", []) if a in VALID_ACTIONS]
        draft["resolution_actions"] = _cap(actions, MAX_ACTIONS)

        # Consistency: action_required iff refund > 0
        refund = draft["financial_resolution"]["recommended_refund_brl"]
        if refund > 0:
            draft["assessment"]["case_status"] = "action_required"
        else:
            draft["assessment"]["case_status"] = "no_action"

        return self.handoff(
            to_agent="coordinator",
            case_id=message.case_id,
            intent="verified_output",
            payload={"output": draft, "verification_issues": issues},
            evidence_ids=draft["evidence_ids"],
        )
