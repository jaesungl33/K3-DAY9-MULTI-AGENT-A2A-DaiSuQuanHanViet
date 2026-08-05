"""Shared schemas for case input, agent handoffs, and final output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseInput:
    case_id: str
    opened_at: str
    claimed_order_id: str
    customer_message: str
    policy_version: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CaseInput:
        req = data["customer_request"]
        return cls(
            case_id=data["case_id"],
            opened_at=data["opened_at"],
            claimed_order_id=req["claimed_order_id"],
            customer_message=req.get("message", ""),
            policy_version=data.get("policy_version", "EC_POLICY_V1"),
        )


@dataclass
class OrderItemRecord:
    order_id: str
    order_item_id: int
    product_id: str
    seller_id: str
    shipping_limit_date: str | None
    price: float
    freight_value: float


@dataclass
class PaymentRecord:
    order_id: str
    payment_sequential: int
    payment_type: str
    payment_installments: int
    payment_value: float


@dataclass
class OrderRecord:
    order_id: str
    customer_id: str
    order_status: str
    order_purchase_timestamp: str | None
    order_delivered_carrier_date: str | None
    order_delivered_customer_date: str | None
    order_estimated_delivery_date: str | None


@dataclass
class OrderSellerReport:
    agent: str = "order_seller_agent"
    order: OrderRecord | None = None
    items: list[OrderItemRecord] = field(default_factory=list)
    seller_ids: list[str] = field(default_factory=list)
    seller_late_handoff: bool = False
    violating_seller_id: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    llm_insight: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentReport:
    agent: str = "payment_agent"
    payments: list[PaymentRecord] = field(default_factory=list)
    payment_total_brl: float = 0.0
    item_total_brl: float = 0.0
    freight_total_brl: float = 0.0
    expected_total_brl: float = 0.0
    payment_matches: bool = False
    has_split_payment: bool = False
    evidence_ids: list[str] = field(default_factory=list)
    llm_insight: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryReport:
    agent: str = "delivery_agent"
    delivered_late: bool = False
    carrier_after_limit: bool = False
    carrier_on_time: bool = False
    estimated_delivery_date: str | None = None
    actual_delivery_date: str | None = None
    carrier_handoff_date: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    llm_insight: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyDecision:
    agent: str = "policy_agent"
    primary_issue: str = ""
    case_status: str = "no_action"
    confidence: float = 0.0
    root_cause_code: str = ""
    responsible_parties: list[dict[str, str]] = field(default_factory=list)
    recommended_refund_brl: float = 0.0
    resolution_actions: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    llm_insight: dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseOutput:
    case_id: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"case_id": self.case_id, **self.payload}
