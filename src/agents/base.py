"""Shared A2A message types and base agent."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class A2AMessage:
    from_agent: str
    to_agent: str
    case_id: str
    intent: str
    payload: dict[str, Any] = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseAgent:
    name: str = "base"
    role: str = "generic"
    data_access: list[str] = []

    def handle(self, message: A2AMessage) -> A2AMessage:
        raise NotImplementedError

    def handoff(
        self,
        to_agent: str,
        case_id: str,
        intent: str,
        payload: dict[str, Any] | None = None,
        evidence_ids: list[str] | None = None,
    ) -> A2AMessage:
        return A2AMessage(
            from_agent=self.name,
            to_agent=to_agent,
            case_id=case_id,
            intent=intent,
            payload=payload or {},
            evidence_ids=evidence_ids or [],
        )
