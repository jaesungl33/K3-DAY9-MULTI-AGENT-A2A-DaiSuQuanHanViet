"""Batch runner for dispute resolution cases."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.agents.base import TraceLogger
from src.agents.coordinator import CoordinatorAgent
from src.llm_client import LLMClient
from src.models import CaseInput

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"


def load_case(path: Path) -> CaseInput:
    with path.open(encoding="utf-8") as handle:
        return CaseInput.from_dict(json.load(handle))


def process_case(case: CaseInput, coordinator: CoordinatorAgent) -> dict:
    result = coordinator.run(case.case_id, {"case_input": case})
    return result["case_output"].to_dict()


def process_all(input_dir: Path = INPUT_DIR, output_dir: Path = OUTPUT_DIR) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    trace = TraceLogger()
    trace.reset()
    llm = LLMClient()
    coordinator = CoordinatorAgent(trace, llm)

    case_files = sorted(input_dir.glob("EC_*.json"))

    def _process_one(case_path: Path) -> str:
        case = load_case(case_path)
        output = process_case(case, coordinator)
        out_path = output_dir / f"{case.case_id}.json"
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(output, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return case.case_id

    with ThreadPoolExecutor(max_workers=4) as executor:
        processed = list(executor.map(_process_one, case_files))

    trace.flush()
    return processed
