from __future__ import annotations

import json
import platform
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .agents import DeliveryAgent, OrderSellerAgent, PaymentAgent, PolicyAgent, VerifierAgent, money
from .repository import OlistRepository, validate_data_files
from .trace import TraceWriter


MODEL_NAME = "deterministic-ec-policy-v1"
MODEL_PARAMETER_SIZE = "0B (rule-based, no trainable parameters)"
FRAMEWORK_NAME = "Custom Python multi-agent orchestrator"
EXPECTED_CASES = tuple(f"EC_{index:03d}.json" for index in range(1, 51))


def validate_project(project_root: Path) -> list[str]:
    errors = validate_data_files(project_root / "data")
    input_dir = project_root / "input"
    existing = {path.name for path in input_dir.glob("EC_*.json")}
    missing = [name for name in EXPECTED_CASES if name not in existing]
    extras = sorted(existing - set(EXPECTED_CASES))
    if missing:
        errors.append(
            f"Missing {len(missing)} official input files in input/: "
            + ", ".join(missing[:5])
            + (" ..." if len(missing) > 5 else "")
        )
    if extras:
        errors.append("Unexpected EC input files: " + ", ".join(extras))
    return errors


def decimal_to_float(value: Decimal) -> float:
    return float(money(value))


def select_evidence(
    order_id: str,
    item_ids: list[str],
    payment_ids: list[str],
    seller_ids: list[str],
    cause_code: str,
) -> list[str]:
    evidence = [f"order:{order_id}"]
    pools = [
        [f"item:{item_id}" for item_id in item_ids],
        [f"payment:{payment_id}" for payment_id in payment_ids],
        [f"seller:{seller_id}" for seller_id in seller_ids],
    ]
    # Preserve at least one evidence item from every available domain.
    for pool in pools:
        if pool and len(evidence) < 9:
            evidence.append(pool.pop(0))
    for pool in pools:
        while pool and len(evidence) < 9:
            evidence.append(pool.pop(0))
    evidence.append(f"policy:{cause_code}")
    return evidence[:10]


class CoordinatorAgent:
    name = "coordinator_agent"

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.repository = OlistRepository(self.project_root / "data")
        self.order_agent = OrderSellerAgent(self.repository)
        self.payment_agent = PaymentAgent(self.repository)
        self.delivery_agent = DeliveryAgent()
        self.policy_agent = PolicyAgent()
        self.verifier_agent = VerifierAgent(self.repository)

    def run(self, zip_output: Path | None = None) -> dict[str, Any]:
        errors = validate_project(self.project_root)
        if errors:
            raise FileNotFoundError("Project validation failed:\n- " + "\n- ".join(errors))

        run_id = uuid.uuid4().hex
        trace = TraceWriter(self.project_root / "logging" / "trace.jsonl", run_id)
        output_dir = self.project_root / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        for old_output in output_dir.glob("EC_*.json"):
            old_output.unlink()

        processed = 0
        issue_counts: dict[str, int] = {}
        for filename in EXPECTED_CASES:
            case_path = self.project_root / "input" / filename
            case = json.loads(case_path.read_text(encoding="utf-8-sig"))
            result = self.resolve_case(case, trace)
            (output_dir / filename).write_text(
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )
            processed += 1
            issue = result["assessment"]["primary_issue"]
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

        metadata = self._write_metadata(run_id, processed, issue_counts)
        if zip_output is not None:
            self._zip_outputs(zip_output)
        return metadata

    def resolve_case(self, case: dict[str, Any], trace: TraceWriter) -> dict[str, Any]:
        case_id = case["case_id"]
        request = case["customer_request"]
        order_id = request["claimed_order_id"]
        if case.get("policy_version") != "EC_POLICY_V1":
            raise ValueError(f"Unsupported policy_version in {case_id}")

        trace.write(
            case_id=case_id,
            from_agent=self.name,
            to_agent=self.order_agent.name,
            event="investigate_order_and_seller",
            payload={"order_id": order_id},
        )
        order_finding = self.order_agent.investigate(order_id)
        trace.write(
            case_id=case_id,
            from_agent=self.order_agent.name,
            to_agent=self.name,
            event="order_seller_finding",
            payload={
                "order_status": order_finding.order.order_status,
                "item_count": len(order_finding.items),
                "seller_ids": list(order_finding.seller_ids),
                "item_total_brl": decimal_to_float(order_finding.item_total),
                "freight_total_brl": decimal_to_float(order_finding.freight_total),
            },
        )

        trace.write(
            case_id=case_id,
            from_agent=self.name,
            to_agent=self.payment_agent.name,
            event="reconcile_payments",
            payload={"order_id": order_id},
        )
        payment_finding = self.payment_agent.reconcile(order_id, order_finding)
        trace.write(
            case_id=case_id,
            from_agent=self.payment_agent.name,
            to_agent=self.name,
            event="payment_finding",
            payload={
                "payment_row_count": len(payment_finding.payments),
                "payment_total_brl": decimal_to_float(payment_finding.payment_total),
                "payment_matches_order_total": payment_finding.payment_matches_order_total,
            },
        )

        trace.write(
            case_id=case_id,
            from_agent=self.name,
            to_agent=self.delivery_agent.name,
            event="analyze_delivery",
            payload={"order_id": order_id},
        )
        delivery_finding = self.delivery_agent.analyze(order_finding)
        trace.write(
            case_id=case_id,
            from_agent=self.delivery_agent.name,
            to_agent=self.name,
            event="delivery_finding",
            payload={
                "delivered_late": delivery_finding.delivered_late,
                "seller_handoff_late": delivery_finding.seller_handoff_late,
                "offending_seller_ids": list(delivery_finding.offending_seller_ids),
            },
        )

        trace.write(
            case_id=case_id,
            from_agent=self.name,
            to_agent=self.policy_agent.name,
            event="apply_policy",
            payload={"policy_version": "EC_POLICY_V1"},
        )
        decision = self.policy_agent.decide(order_finding, payment_finding, delivery_finding)

        item_ids = [f"{item.order_id}:{item.order_item_id}" for item in order_finding.items][:5]
        seller_ids = list(order_finding.seller_ids)[:5]
        payment_ids = [
            f"{payment.order_id}:{payment.payment_sequential}"
            for payment in payment_finding.payments
        ][:5]
        output = {
            "case_id": case_id,
            "assessment": {
                "primary_issue": decision.primary_issue,
                "case_status": decision.case_status,
                "confidence": decision.confidence,
            },
            "affected_entities": {
                "order_ids": [order_id],
                "item_ids": item_ids,
                "seller_ids": seller_ids,
                "payment_ids": payment_ids,
            },
            "root_cause_analysis": {
                "ranked_causes": [{"cause_code": decision.cause_code, "rank": 1}],
                "responsible_parties": list(decision.responsible_parties),
            },
            "evidence_ids": select_evidence(
                order_id, item_ids, payment_ids, seller_ids, decision.cause_code
            ),
            "financial_resolution": {
                "currency": "BRL",
                "item_total_brl": decimal_to_float(order_finding.item_total),
                "freight_total_brl": decimal_to_float(order_finding.freight_total),
                "payment_total_brl": decimal_to_float(payment_finding.payment_total),
                "recommended_refund_brl": decimal_to_float(decision.recommended_refund),
            },
            "resolution_actions": list(decision.resolution_actions),
        }
        trace.write(
            case_id=case_id,
            from_agent=self.policy_agent.name,
            to_agent=self.name,
            event="policy_decision",
            payload={
                "primary_issue": decision.primary_issue,
                "cause_code": decision.cause_code,
                "recommended_refund_brl": decimal_to_float(decision.recommended_refund),
            },
        )

        trace.write(
            case_id=case_id,
            from_agent=self.name,
            to_agent=self.verifier_agent.name,
            event="verify_output",
            payload={"order_id": order_id},
        )
        self.verifier_agent.verify(output, case_id, order_id)
        trace.write(
            case_id=case_id,
            from_agent=self.verifier_agent.name,
            to_agent=self.name,
            event="verification_passed",
            payload={"schema_valid": True, "evidence_valid": True, "money_valid": True},
        )
        return output

    def _write_metadata(
        self, run_id: str, case_count: int, issue_counts: dict[str, int]
    ) -> dict[str, Any]:
        metadata = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": {
                "name": MODEL_NAME,
                "parameter_size": MODEL_PARAMETER_SIZE,
                "provider": "local",
            },
            "framework": FRAMEWORK_NAME,
            "runtime": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
            },
            "policy_version": "EC_POLICY_V1",
            "case_count": case_count,
            "issue_counts": dict(sorted(issue_counts.items())),
            "trace_file": "logging/trace.jsonl",
            "output_directory": "output",
        }
        path = self.project_root / "logging" / "metadata.json"
        path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return metadata

    def _zip_outputs(self, zip_path: Path) -> None:
        zip_path = zip_path.resolve()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for filename in EXPECTED_CASES:
                path = self.project_root / "output" / filename
                archive.write(path, arcname=filename)
