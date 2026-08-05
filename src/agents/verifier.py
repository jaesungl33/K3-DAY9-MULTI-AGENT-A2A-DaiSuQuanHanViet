"""Validate output schema, evidence IDs, and numeric limits."""

from __future__ import annotations

from typing import Any

from src.agents.base import BaseAgent
from src.data_loader import evidence_exists, round_brl
from src.prompts import VERIFIER_SYSTEM


class VerifierAgent(BaseAgent):
    name = "verifier_agent"

    MAX_EVIDENCE = 10
    MAX_ENTITIES = 5
    MAX_CAUSES = 3
    MAX_PARTIES = 3
    MAX_ACTIONS = 5

    def run(self, case_id: str, context: dict[str, Any]) -> dict[str, Any]:
        output = context["draft_output"]
        errors: list[str] = []

        assessment = output.get("assessment", {})
        confidence = assessment.get("confidence", 0)
        if not (0 <= confidence <= 1):
            errors.append("confidence_out_of_range")

        entities = output.get("affected_entities", {})
        for key in ("order_ids", "item_ids", "seller_ids", "payment_ids"):
            values = entities.get(key, [])
            if len(values) > self.MAX_ENTITIES:
                errors.append(f"{key}_limit_exceeded")

        evidence_ids = output.get("evidence_ids", [])
        if len(evidence_ids) > self.MAX_EVIDENCE:
            errors.append("evidence_limit_exceeded")

        for evidence_id in evidence_ids:
            if not evidence_exists(evidence_id):
                errors.append(f"invalid_evidence:{evidence_id}")

        causes = output.get("root_cause_analysis", {}).get("ranked_causes", [])
        if len(causes) > self.MAX_CAUSES:
            errors.append("causes_limit_exceeded")

        parties = output.get("root_cause_analysis", {}).get("responsible_parties", [])
        if len(parties) > self.MAX_PARTIES:
            errors.append("parties_limit_exceeded")

        actions = output.get("resolution_actions", [])
        if len(actions) > self.MAX_ACTIONS:
            errors.append("actions_limit_exceeded")

        financial = output.get("financial_resolution", {})
        for key in (
            "item_total_brl",
            "freight_total_brl",
            "payment_total_brl",
            "recommended_refund_brl",
        ):
            if key in financial:
                financial[key] = round_brl(financial[key])

        llm_insight = self._llm_analyze(
            case_id,
            VERIFIER_SYSTEM,
            {"draft_output": output, "validation_errors": errors},
        )

        verified = len(errors) == 0
        result = {
            "verified_output": output,
            "verification_passed": verified,
            "errors": errors,
            "llm_insight": llm_insight,
        }
        self.trace.log(case_id, "verification", self.name, None, result)
        return result
