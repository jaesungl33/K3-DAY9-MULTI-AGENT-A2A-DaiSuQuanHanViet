from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class OrderRecord:
    order_id: str
    customer_id: str
    order_status: str
    delivered_carrier_at: datetime | None
    delivered_customer_at: datetime | None
    estimated_delivery_at: datetime | None


@dataclass(frozen=True)
class ItemRecord:
    order_id: str
    order_item_id: int
    product_id: str
    seller_id: str
    shipping_limit_at: datetime | None
    price: Decimal
    freight_value: Decimal


@dataclass(frozen=True)
class PaymentRecord:
    order_id: str
    payment_sequential: int
    payment_type: str
    payment_installments: int
    payment_value: Decimal


@dataclass(frozen=True)
class OrderSellerFinding:
    order: OrderRecord
    items: tuple[ItemRecord, ...]
    seller_ids: tuple[str, ...]
    item_total: Decimal
    freight_total: Decimal


@dataclass(frozen=True)
class PaymentFinding:
    payments: tuple[PaymentRecord, ...]
    payment_total: Decimal
    payment_matches_order_total: bool
    is_split_payment: bool


@dataclass(frozen=True)
class DeliveryFinding:
    delivered_late: bool
    delivered_within_estimate: bool
    seller_handoff_late: bool
    offending_seller_ids: tuple[str, ...]
    offending_item_ids: tuple[str, ...]


@dataclass(frozen=True)
class PolicyDecision:
    primary_issue: str
    case_status: str
    confidence: float
    cause_code: str
    responsible_parties: tuple[dict[str, str], ...]
    recommended_refund: Decimal
    resolution_actions: tuple[str, ...]


JsonObject = dict[str, Any]
