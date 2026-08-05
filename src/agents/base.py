"""Base agent utilities and trace logging."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRACE_PATH = Path(__file__).resolve().parent.parent.parent / "trace.jsonl"


def _serialize(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


class TraceLogger:
    def __init__(self, path: Path = TRACE_PATH) -> None:
        self.path = path
        self._events: list[dict[str, Any]] = []

    def reset(self) -> None:
        self._events = []

    def log(
        self,
        case_id: str,
        event_type: str,
        from_agent: str,
        to_agent: str | None,
        payload: Any,
    ) -> None:
        self._events.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "case_id": case_id,
                "event_type": event_type,
                "from_agent": from_agent,
                "to_agent": to_agent,
                "payload": _serialize(payload),
            }
        )

    def flush(self) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            for event in self._events:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")


class BaseAgent(ABC):
    name: str

    def __init__(self, trace: TraceLogger, llm: Any | None = None) -> None:
        self.trace = trace
        self.llm = llm

    @abstractmethod
    def run(self, case_id: str, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def _llm_analyze(self, case_id: str, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.llm is None:
            return {}
        result = self.llm.analyze(self.name, system_prompt, payload)
        self.trace.log(case_id, "llm_call", self.name, None, result)
        return result
