from __future__ import annotations

import sys
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecommerce_a2a.agents import PolicyAgent
from ecommerce_a2a.models import (
    DeliveryFinding,
    ItemRecord,
    OrderRecord,
    OrderSellerFinding,
    PaymentFinding,
    PaymentRecord,
)


class PolicyAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = PolicyAgent()
        self.item = ItemRecord(
            order_id="o1",
            order_item_id=1,
            product_id="p1",
            seller_id="s1",
            shipping_limit_at=datetime(2018, 1, 5),
            price=Decimal("100.00"),
            freight_value=Decimal("15.00"),
        )
        self.payment = PaymentRecord(
            order_id="o1",
            payment_sequential=1,
            payment_type="credit_card",
            payment_installments=1,
            payment_value=Decimal("115.00"),
        )

    def order_finding(self, status: str = "delivered") -> OrderSellerFinding:
        return OrderSellerFinding(
            order=OrderRecord(
                order_id="o1",
                customer_id="c1",
                order_status=status,
                delivered_carrier_at=datetime(2018, 1, 6),
                delivered_customer_at=datetime(2018, 1, 12),
                estimated_delivery_at=datetime(2018, 1, 10),
            ),
            items=(self.item,),
            seller_ids=("s1",),
            item_total=Decimal("100.00"),
            freight_total=Decimal("15.00"),
        )

    def payment_finding(self, rows: int = 1, matches: bool = True) -> PaymentFinding:
        payments = tuple(self.payment for _ in range(rows))
        return PaymentFinding(
            payments=payments,
            payment_total=Decimal("115.00"),
            payment_matches_order_total=matches,
            is_split_payment=rows >= 2,
        )

    def delivery(self, *, late: bool, seller_late: bool, within: bool = False) -> DeliveryFinding:
        return DeliveryFinding(
            delivered_late=late,
            delivered_within_estimate=within,
            seller_handoff_late=seller_late,
            offending_seller_ids=("s1",) if seller_late else (),
            offending_item_ids=("o1:1",) if seller_late else (),
        )

    def test_priority_canceled_paid(self) -> None:
        decision = self.policy.decide(
            self.order_finding("canceled"), self.payment_finding(), self.delivery(late=True, seller_late=True)
        )
        self.assertEqual(decision.primary_issue, "canceled_order_paid")
        self.assertEqual(decision.recommended_refund, Decimal("115.00"))

    def test_unavailable_paid(self) -> None:
        decision = self.policy.decide(
            self.order_finding("unavailable"), self.payment_finding(), self.delivery(late=False, seller_late=False)
        )
        self.assertEqual(decision.primary_issue, "unavailable_order_paid")

    def test_late_delivery_seller(self) -> None:
        decision = self.policy.decide(
            self.order_finding(), self.payment_finding(), self.delivery(late=True, seller_late=True)
        )
        self.assertEqual(decision.primary_issue, "late_delivery_seller")
        self.assertEqual(decision.recommended_refund, Decimal("15.00"))

    def test_late_delivery_logistics(self) -> None:
        decision = self.policy.decide(
            self.order_finding(), self.payment_finding(), self.delivery(late=True, seller_late=False)
        )
        self.assertEqual(decision.primary_issue, "late_delivery_logistics")

    def test_valid_split_payment(self) -> None:
        decision = self.policy.decide(
            self.order_finding(), self.payment_finding(rows=2), self.delivery(late=False, seller_late=False)
        )
        self.assertEqual(decision.primary_issue, "valid_split_payment")
        self.assertEqual(decision.case_status, "no_action")

    def test_unsupported_late_claim(self) -> None:
        decision = self.policy.decide(
            self.order_finding(), self.payment_finding(), self.delivery(late=False, seller_late=False, within=True)
        )
        self.assertEqual(decision.primary_issue, "unsupported_late_claim")


if __name__ == "__main__":
    unittest.main()
