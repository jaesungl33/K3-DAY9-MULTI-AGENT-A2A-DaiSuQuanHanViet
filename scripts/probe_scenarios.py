#!/usr/bin/env python3
"""Discover sample orders matching each EC policy scenario for local testing."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main() -> None:
    orders = pd.read_csv(DATA / "olist_orders_dataset.csv")
    items = pd.read_csv(DATA / "olist_order_items_dataset.csv")
    payments = pd.read_csv(DATA / "olist_order_payments_dataset.csv")

    orders["carrier_ts"] = pd.to_datetime(orders["order_delivered_carrier_date"], errors="coerce")
    orders["customer_ts"] = pd.to_datetime(orders["order_delivered_customer_date"], errors="coerce")
    orders["estimate_ts"] = pd.to_datetime(orders["order_estimated_delivery_date"], errors="coerce")

    item_agg = items.groupby("order_id").agg(
        limit_ts=("shipping_limit_date", "min"),
        item_total=("price", "sum"),
        freight_total=("freight_value", "sum"),
    )
    pay_agg = payments.groupby("order_id").agg(
        payment_total=("payment_value", "sum"),
        payment_rows=("payment_sequential", "count"),
    )

    df = orders.join(item_agg, on="order_id").join(pay_agg, on="order_id")
    df["limit_ts"] = pd.to_datetime(df["limit_ts"], errors="coerce")
    df["delivered_late"] = df["customer_ts"] > df["estimate_ts"]
    df["seller_late"] = df["carrier_ts"] > df["limit_ts"]
    df["expected_total"] = df["item_total"].fillna(0) + df["freight_total"].fillna(0)
    df["payment_matches"] = (df["payment_total"] - df["expected_total"]).abs() <= 0.10

    scenarios = {
        "canceled_order_paid": df[(df["order_status"] == "canceled") & (df["payment_total"] > 0)],
        "unavailable_order_paid": df[(df["order_status"] == "unavailable") & (df["payment_total"] > 0)],
        "late_delivery_seller": df[df["delivered_late"] & df["seller_late"]],
        "late_delivery_logistics": df[df["delivered_late"] & ~df["seller_late"].fillna(False)],
        "valid_split_payment": df[(df["payment_rows"] >= 2) & df["payment_matches"]],
        "unsupported_late_claim": df[~df["delivered_late"].fillna(True) & df["payment_matches"]],
    }

    for name, subset in scenarios.items():
        count = len(subset)
        sample = subset["order_id"].iloc[0] if count else None
        print(f"{name}: {count} orders, sample={sample}")


if __name__ == "__main__":
    main()
