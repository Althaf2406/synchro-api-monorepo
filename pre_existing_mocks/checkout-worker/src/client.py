"""
pre_existing_mocks/checkout-worker/src/client.py
Downstream Repo 1 HTTP Client & Transactional Fee Calculation calling POST /v2/charges.
"""

from typing import Any, Callable, Dict
from src.models import ChargePayload, ChargeResult


def build_and_parse_charge(
    customer_id: str,
    dollar_amount: float,
    mock_http_post: Callable[[str, Dict[str, Any]], Dict[str, Any]],
) -> bool:
    """
    Converts dollar amount to minor units (cents), submits charge payload to /v2/charges,
    and verifies the transaction succeeded with matching net amount.
    """
    cents = int(round(dollar_amount * 100))
    payload = ChargePayload(customer_id=customer_id, amount_cents=cents)
    raw_resp = mock_http_post("/v2/charges", payload.model_dump())
    result = ChargeResult(**raw_resp)
    return result.status == "CHARGED" and result.net_amount_cents == cents
