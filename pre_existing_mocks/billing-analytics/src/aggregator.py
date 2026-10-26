"""
pre_existing_mocks/billing-analytics/src/aggregator.py
Downstream Repo 2 Multi-Hop Settlement Aggregator (2 hops away from POST /v2/charges).
"""

from typing import Any, Dict, List
from src.schemas import SettlementEventRecord


def parse_charge_event(raw_event: Dict[str, Any]) -> SettlementEventRecord:
    """
    Maps a raw charge event dictionary into a validated SettlementEventRecord DTO.
    """
    return SettlementEventRecord(
        transaction_id=str(raw_event["transaction_id"]),
        customer_id=str(raw_event["customer_id"]),
        status=str(raw_event["status"]),
        amount_cents=int(raw_event["amount_cents"]),
    )


def calculate_daily_settled_volume_cents(events: List[Dict[str, Any]]) -> int:
    """
    Multi-hop consumer function: calls parse_charge_event() and aggregates
    all settled transactions ('CHARGED' in v1 contract) in minor units.
    """
    total_cents = 0
    for ev in events:
        record = parse_charge_event(ev)
        if record.status == "CHARGED":
            total_cents += record.amount_cents
    return total_cents
