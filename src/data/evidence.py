"""Build issue-aware evidence_ids to maximize precision vs gold labels.

False-positive rule from the brief: evidence not needed / wrong format hurts score.
Seller evidence is only relevant when the responsible party is a seller.
"""

from __future__ import annotations

from src.config import MAX_EVIDENCE_IDS
from src.data.policy import PolicyDecision
from src.data.store import OrderBundle


def build_evidence_ids(bundle: OrderBundle, decision: PolicyDecision) -> list[str]:
    order_id = bundle.order_id
    evidence: list[str] = [f"order:{order_id}"]

    for item in bundle.items:
        evidence.append(f"item:{order_id}:{item['order_item_id']}")

    for payment in bundle.payments:
        evidence.append(f"payment:{order_id}:{payment['payment_sequential']}")

    # Only attach seller evidence when seller is actually responsible.
    if decision.primary_issue == "late_delivery_seller":
        for party in decision.responsible_parties:
            if party.get("party_type") == "seller" and party.get("party_id"):
                sid = f"seller:{party['party_id']}"
                if sid not in evidence:
                    evidence.append(sid)

    policy_id = f"policy:{decision.cause_code}"
    evidence.append(policy_id)

    # Deduplicate, preserve order; never drop policy when capping at 10.
    seen: set[str] = set()
    unique: list[str] = []
    for eid in evidence:
        if eid not in seen:
            seen.add(eid)
            unique.append(eid)

    if len(unique) <= MAX_EVIDENCE_IDS:
        return unique

    policy = [e for e in unique if e.startswith("policy:")]
    rest = [e for e in unique if not e.startswith("policy:")]
    kept = rest[: MAX_EVIDENCE_IDS - len(policy)] + policy
    return kept[:MAX_EVIDENCE_IDS]


def seller_ids_for_entities(decision: PolicyDecision, fallback_seller_ids: list[str]) -> list[str]:
    """Keep seller entity IDs only when the case blames a seller."""
    if decision.primary_issue != "late_delivery_seller":
        return []
    responsible = [
        p["party_id"]
        for p in decision.responsible_parties
        if p.get("party_type") == "seller" and p.get("party_id")
    ]
    return responsible[:5] if responsible else fallback_seller_ids[:5]
