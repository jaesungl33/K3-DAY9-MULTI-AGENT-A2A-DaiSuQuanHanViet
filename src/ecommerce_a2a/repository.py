from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import ItemRecord, OrderRecord, PaymentRecord


REQUIRED_DATA_FILES = {
    "olist_customers_dataset.csv": {
        "customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"
    },
    "olist_geolocation_dataset.csv": {
        "geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"
    },
    "olist_order_items_dataset.csv": {
        "order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"
    },
    "olist_order_payments_dataset.csv": {
        "order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"
    },
    "olist_order_reviews_dataset.csv": {
        "review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
        "review_creation_date", "review_answer_timestamp"
    },
    "olist_orders_dataset.csv": {
        "order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"
    },
    "olist_products_dataset.csv": {
        "product_id", "product_category_name", "product_name_lenght", "product_description_lenght",
        "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"
    },
    "olist_sellers_dataset.csv": {
        "seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"
    },
    "product_category_name_translation.csv": {
        "product_category_name", "product_category_name_english"
    },
}


def parse_datetime(value: str | None) -> datetime | None:
    text = (value or "").strip()
    return datetime.fromisoformat(text) if text else None


def parse_decimal(value: str | None, field: str) -> Decimal:
    try:
        return Decimal((value or "0").strip() or "0")
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal in {field}: {value!r}") from exc


def normalize_header(name: str) -> str:
    return name.lstrip("\ufeff").strip()


def validate_data_files(data_dir: Path) -> list[str]:
    errors: list[str] = []
    for filename, required_columns in REQUIRED_DATA_FILES.items():
        path = data_dir / filename
        if not path.is_file():
            errors.append(f"Missing data file: data/{filename}")
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            try:
                header = {normalize_header(col) for col in next(reader)}
            except StopIteration:
                errors.append(f"Empty data file: data/{filename}")
                continue
        missing_columns = sorted(required_columns - header)
        if missing_columns:
            errors.append(f"data/{filename} missing columns: {', '.join(missing_columns)}")
    return errors


class OlistRepository:
    """Read-only repository used by domain agents.

    Only the four tables needed by EC_POLICY_V1 are loaded into memory. The
    remaining Olist CSV files are still validated and retained in the repo.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        errors = validate_data_files(data_dir)
        if errors:
            raise FileNotFoundError("\n".join(errors))

        self.orders: dict[str, OrderRecord] = {}
        self.items_by_order: dict[str, list[ItemRecord]] = defaultdict(list)
        self.payments_by_order: dict[str, list[PaymentRecord]] = defaultdict(list)
        self.seller_ids: set[str] = set()
        self._load_orders()
        self._load_items()
        self._load_payments()
        self._load_sellers()

    def _load_orders(self) -> None:
        path = self.data_dir / "olist_orders_dataset.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                record = OrderRecord(
                    order_id=row["order_id"],
                    customer_id=row["customer_id"],
                    order_status=row["order_status"],
                    delivered_carrier_at=parse_datetime(row["order_delivered_carrier_date"]),
                    delivered_customer_at=parse_datetime(row["order_delivered_customer_date"]),
                    estimated_delivery_at=parse_datetime(row["order_estimated_delivery_date"]),
                )
                self.orders[record.order_id] = record

    def _load_items(self) -> None:
        path = self.data_dir / "olist_order_items_dataset.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                record = ItemRecord(
                    order_id=row["order_id"],
                    order_item_id=int(row["order_item_id"]),
                    product_id=row["product_id"],
                    seller_id=row["seller_id"],
                    shipping_limit_at=parse_datetime(row["shipping_limit_date"]),
                    price=parse_decimal(row["price"], "price"),
                    freight_value=parse_decimal(row["freight_value"], "freight_value"),
                )
                self.items_by_order[record.order_id].append(record)

        for records in self.items_by_order.values():
            records.sort(key=lambda item: item.order_item_id)

    def _load_payments(self) -> None:
        path = self.data_dir / "olist_order_payments_dataset.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                record = PaymentRecord(
                    order_id=row["order_id"],
                    payment_sequential=int(row["payment_sequential"]),
                    payment_type=row["payment_type"],
                    payment_installments=int(row["payment_installments"]),
                    payment_value=parse_decimal(row["payment_value"], "payment_value"),
                )
                self.payments_by_order[record.order_id].append(record)

        for records in self.payments_by_order.values():
            records.sort(key=lambda payment: payment.payment_sequential)

    def _load_sellers(self) -> None:
        path = self.data_dir / "olist_sellers_dataset.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            self.seller_ids = {row["seller_id"] for row in csv.DictReader(handle)}

    def get_order(self, order_id: str) -> OrderRecord:
        try:
            return self.orders[order_id]
        except KeyError as exc:
            raise KeyError(f"Order not found in Olist data: {order_id}") from exc

    def get_items(self, order_id: str) -> tuple[ItemRecord, ...]:
        return tuple(self.items_by_order.get(order_id, ()))

    def get_payments(self, order_id: str) -> tuple[PaymentRecord, ...]:
        return tuple(self.payments_by_order.get(order_id, ()))
