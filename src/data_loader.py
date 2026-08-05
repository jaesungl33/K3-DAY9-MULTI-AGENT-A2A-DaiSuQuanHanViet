"""Load and query Olist CSV datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.models import OrderItemRecord, OrderRecord, PaymentRecord

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_ORDERS: pd.DataFrame | None = None
_ITEMS: pd.DataFrame | None = None
_PAYMENTS: pd.DataFrame | None = None


def _load_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    global _ORDERS, _ITEMS, _PAYMENTS
    if _ORDERS is None:
        _ORDERS = pd.read_csv(DATA_DIR / "olist_orders_dataset.csv")
        _ITEMS = pd.read_csv(DATA_DIR / "olist_order_items_dataset.csv")
        _PAYMENTS = pd.read_csv(DATA_DIR / "olist_order_payments_dataset.csv")
    return _ORDERS, _ITEMS, _PAYMENTS


def round_brl(value: float) -> float:
    return round(float(value), 2)


def parse_ts(value: object) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return pd.Timestamp(text)


def ts_to_str(value: pd.Timestamp | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value)


def get_order(order_id: str) -> OrderRecord | None:
    orders, _, _ = _load_frames()
    rows = orders.loc[orders["order_id"] == order_id]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return OrderRecord(
        order_id=str(row["order_id"]),
        customer_id=str(row["customer_id"]),
        order_status=str(row["order_status"]),
        order_purchase_timestamp=ts_to_str(parse_ts(row["order_purchase_timestamp"])),
        order_delivered_carrier_date=ts_to_str(parse_ts(row["order_delivered_carrier_date"])),
        order_delivered_customer_date=ts_to_str(parse_ts(row["order_delivered_customer_date"])),
        order_estimated_delivery_date=ts_to_str(parse_ts(row["order_estimated_delivery_date"])),
    )


def get_order_items(order_id: str) -> list[OrderItemRecord]:
    _, items, _ = _load_frames()
    rows = items.loc[items["order_id"] == order_id].sort_values("order_item_id")
    records: list[OrderItemRecord] = []
    for _, row in rows.iterrows():
        records.append(
            OrderItemRecord(
                order_id=str(row["order_id"]),
                order_item_id=int(row["order_item_id"]),
                product_id=str(row["product_id"]),
                seller_id=str(row["seller_id"]),
                shipping_limit_date=ts_to_str(parse_ts(row["shipping_limit_date"])),
                price=round_brl(row["price"]),
                freight_value=round_brl(row["freight_value"]),
            )
        )
    return records


def get_payments(order_id: str) -> list[PaymentRecord]:
    _, _, payments = _load_frames()
    rows = payments.loc[payments["order_id"] == order_id].sort_values("payment_sequential")
    records: list[PaymentRecord] = []
    for _, row in rows.iterrows():
        records.append(
            PaymentRecord(
                order_id=str(row["order_id"]),
                payment_sequential=int(row["payment_sequential"]),
                payment_type=str(row["payment_type"]),
                payment_installments=int(row["payment_installments"]),
                payment_value=round_brl(row["payment_value"]),
            )
        )
    return records


def evidence_exists(evidence_id: str) -> bool:
    if evidence_id.startswith("policy:"):
        return evidence_id.split(":", 1)[1] in {
            "SELLER_HANDOFF_AFTER_LIMIT",
            "CARRIER_DELIVERED_AFTER_ESTIMATE",
            "ORDER_CANCELED_AFTER_PAYMENT",
            "ORDER_UNAVAILABLE_AFTER_PAYMENT",
            "MULTIPLE_PAYMENTS_RECONCILED",
            "DELIVERY_WITHIN_ESTIMATE",
        }

    parts = evidence_id.split(":")
    kind = parts[0]
    orders, items, payments = _load_frames()

    if kind == "order":
        return not orders.loc[orders["order_id"] == parts[1]].empty

    if kind == "item":
        order_id, item_id = parts[1], int(parts[2])
        mask = (items["order_id"] == order_id) & (items["order_item_id"] == item_id)
        return not items.loc[mask].empty

    if kind == "payment":
        order_id, seq = parts[1], int(parts[2])
        mask = (payments["order_id"] == order_id) & (payments["payment_sequential"] == seq)
        return not payments.loc[mask].empty

    if kind == "seller":
        sellers = pd.read_csv(DATA_DIR / "olist_sellers_dataset.csv")
        return not sellers.loc[sellers["seller_id"] == parts[1]].empty

    return False
