"""
pre_existing_mocks/billing-analytics/tests/test_aggregator.py
Unit test suite for billing-analytics ledger aggregation.
"""

from src.aggregator import calculate_daily_settled_volume_cents


def test_calculate_daily_settled_volume_cents() -> None:
    sample_events = [
        {
            "transaction_id": "tx_1",
            "customer_id": "c_101",
            "status": "CHARGED",
            "amount_cents": 2500,
        },
        {
            "transaction_id": "tx_2",
            "customer_id": "c_102",
            "status": "FAILED",
            "amount_cents": 9900,
        },
        {
            "transaction_id": "tx_3",
            "customer_id": "c_103",
            "status": "CHARGED",
            "amount_cents": 1500,
        },
    ]
    total = calculate_daily_settled_volume_cents(sample_events)
    assert total == 4000
