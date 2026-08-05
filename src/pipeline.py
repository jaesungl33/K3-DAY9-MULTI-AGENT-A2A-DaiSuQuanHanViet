"""Batch pipeline: process all input cases -> output/ + logging/trace.jsonl."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from src.agents.coordinator import CoordinatorAgent
from src.config import (
    FRAMEWORK,
    INPUT_DIR,
    LOGGING_DIR,
    MODEL_NAME,
    MODEL_PARAMETER_SIZE,
    OUTPUT_DIR,
    RUNTIME,
)
from src.data.store import get_store


def load_cases(input_dir: Path = INPUT_DIR) -> list[Path]:
    files = sorted(input_dir.glob("EC_*.json"))
    return files


def write_metadata() -> None:
    LOGGING_DIR.mkdir(parents=True, exist_ok=True)
    meta = {
        "model_name": MODEL_NAME,
        "parameter_size": MODEL_PARAMETER_SIZE,
        "framework": FRAMEWORK,
        "runtime": RUNTIME,
        "policy_version": "EC_POLICY_V1",
        "agents": [
            {
                "name": "coordinator",
                "model": MODEL_NAME,
                "role": "orchestration and final assembly",
            },
            {
                "name": "order_seller_agent",
                "model": MODEL_NAME,
                "role": "order/item/seller inspection",
            },
            {
                "name": "payment_agent",
                "model": MODEL_NAME,
                "role": "payment reconciliation",
            },
            {
                "name": "delivery_agent",
                "model": MODEL_NAME,
                "role": "delivery SLA analysis",
            },
            {
                "name": "policy_agent",
                "model": MODEL_NAME,
                "role": "EC_POLICY_V1 decision",
            },
            {
                "name": "verifier_agent",
                "model": MODEL_NAME,
                "role": "schema and evidence verification",
            },
        ],
        "decision_mode": "deterministic_policy_with_a2a_handoffs",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (LOGGING_DIR / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run_pipeline(input_dir: Path = INPUT_DIR, output_dir: Path = OUTPUT_DIR) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    LOGGING_DIR.mkdir(parents=True, exist_ok=True)
    write_metadata()

    store = get_store()
    coordinator = CoordinatorAgent(store)
    case_files = load_cases(input_dir)
    if not case_files:
        raise FileNotFoundError(
            f"No EC_*.json found in {input_dir}. Place official inputs there, "
            "or run: python scripts/generate_inputs.py"
        )

    # Fresh run only — overwrite trace, do not append previous runs
    trace_path = LOGGING_DIR / "trace.jsonl"
    started = time.time()
    summary = {"processed": 0, "by_issue": {}, "errors": []}

    with trace_path.open("w", encoding="utf-8") as trace_f:
        for path in case_files:
            case = json.loads(path.read_text(encoding="utf-8"))
            case_id = case["case_id"]
            t0 = time.time()
            try:
                output, handoffs = coordinator.resolve_case(case)
                out_path = output_dir / f"{case_id}.json"
                out_path.write_text(
                    json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                issue = output["assessment"]["primary_issue"]
                summary["by_issue"][issue] = summary["by_issue"].get(issue, 0) + 1
                summary["processed"] += 1
                event = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "case_id": case_id,
                    "order_id": case["customer_request"]["claimed_order_id"],
                    "status": "ok",
                    "primary_issue": issue,
                    "elapsed_ms": int((time.time() - t0) * 1000),
                    "handoffs": handoffs,
                    "output_file": str(out_path.name),
                }
            except Exception as exc:  # noqa: BLE001
                summary["errors"].append({"case_id": case_id, "error": str(exc)})
                event = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "case_id": case_id,
                    "status": "error",
                    "error": str(exc),
                }
            trace_f.write(json.dumps(event, ensure_ascii=False) + "\n")

    summary["elapsed_sec"] = round(time.time() - started, 3)
    summary["trace_file"] = str(trace_path)
    return summary
