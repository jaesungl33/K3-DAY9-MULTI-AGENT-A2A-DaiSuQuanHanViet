"""Olist CSV data access layer with order-centric joins."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import pandas as pd

from src.config import DATA_DIR, MONEY_ROUND


def _round_money(value: float) -> float:
    return round(float(value), MONEY_ROUND)


@dataclass
class OrderBundle:
    order_id: str
    order: dict[str, Any]
    items: list[dict[str, Any]] = field(default_factory=list)
    payments: list[dict[str, Any]] = field(default_factory=list)
    sellers: list[dict[str, Any]] = field(default_factory=list)

    @property
    def order_status(self) -> str:
        return str(self.order.get("order_status") or "")

    @property
    def item_total_brl(self) -> float:
        return _round_money(sum(float(i.get("price") or 0) for i in self.items))

    @property
    def freight_total_brl(self) -> float:
        return _round_money(sum(float(i.get("freight_value") or 0) for i in self.items))

    @property
    def payment_total_brl(self) -> float:
        return _round_money(sum(float(p.get("payment_value") or 0) for p in self.payments))

    @property
    def expected_total_brl(self) -> float:
        return _round_money(self.item_total_brl + self.freight_total_brl)


class DataStore:
    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        self.orders = pd.read_csv(data_dir / "olist_orders_dataset.csv", dtype=str)
        self.items = pd.read_csv(data_dir / "olist_order_items_dataset.csv", dtype=str)
        self.payments = pd.read_csv(data_dir / "olist_order_payments_dataset.csv", dtype=str)
        self.sellers = pd.read_csv(data_dir / "olist_sellers_dataset.csv", dtype=str)

        for col in (
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ):
            self.orders[col] = pd.to_datetime(self.orders[col], errors="coerce")

        self.items["shipping_limit_date"] = pd.to_datetime(
            self.items["shipping_limit_date"], errors="coerce"
        )
        self.items["price"] = pd.to_numeric(self.items["price"], errors="coerce").fillna(0.0)
        self.items["freight_value"] = pd.to_numeric(
            self.items["freight_value"], errors="coerce"
        ).fillna(0.0)
        self.payments["payment_value"] = pd.to_numeric(
            self.payments["payment_value"], errors="coerce"
        ).fillna(0.0)
        self.payments["payment_sequential"] = pd.to_numeric(
            self.payments["payment_sequential"], errors="coerce"
        ).fillna(1).astype(int)
        self.items["order_item_id"] = pd.to_numeric(
            self.items["order_item_id"], errors="coerce"
        ).fillna(1).astype(int)

        self._orders_by_id = {r["order_id"]: r for r in self.orders.to_dict("records")}
        self._items_by_order: dict[str, list] = {}
        for row in self.items.to_dict("records"):
            self._items_by_order.setdefault(row["order_id"], []).append(row)
        self._payments_by_order: dict[str, list] = {}
        for row in self.payments.to_dict("records"):
            self._payments_by_order.setdefault(row["order_id"], []).append(row)
        self._sellers_by_id = {r["seller_id"]: r for r in self.sellers.to_dict("records")}

    def get_order_bundle(self, order_id: str) -> OrderBundle | None:
        order = self._orders_by_id.get(order_id)
        if order is None:
            return None
        items = sorted(
            self._items_by_order.get(order_id, []),
            key=lambda x: int(x.get("order_item_id") or 0),
        )
        payments = sorted(
            self._payments_by_order.get(order_id, []),
            key=lambda x: int(x.get("payment_sequential") or 0),
        )
        seller_ids = []
        for item in items:
            sid = item.get("seller_id")
            if sid and sid not in seller_ids:
                seller_ids.append(sid)
        sellers = [self._sellers_by_id[s] for s in seller_ids if s in self._sellers_by_id]
        return OrderBundle(
            order_id=order_id,
            order=order,
            items=items,
            payments=payments,
            sellers=sellers,
        )


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    return DataStore()
