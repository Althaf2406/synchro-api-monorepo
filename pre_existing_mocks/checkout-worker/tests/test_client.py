"""
pre_existing_mocks/checkout-worker/tests/test_client.py
Unit test suite for checkout-worker (passes on v1 contract, fails when v2 contract is enforced).
"""

from typing import Any, Dict
from src.client import build_and_parse_charge


def test_build_and_parse_charge_success() -> None:
    captured_endpoint = ""
    captured_payload: Dict[str, Any] = {}

    def mock_post(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal captured_endpoint, captured_payload
        captured_endpoint = endpoint
        captured_payload = payload
        return {
            "transaction_id": "txn_9901",
            "status": "CHARGED",
            "net_amount_cents": payload["amount_cents"],
        }

    ok = build_and_parse_charge("cust_42", 19.99, mock_post)
    assert ok is True
    assert captured_endpoint == "/v2/charges"
    assert captured_payload["customer_id"] == "cust_42"
    assert captured_payload["amount_cents"] == 1999
