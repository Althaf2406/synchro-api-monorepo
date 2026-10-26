"""
pre_existing_mocks/checkout-worker/src/models.py
Downstream Repo 1 DTO definitions mapped to upstream payment-core-api v1 contract.
"""

from pydantic import BaseModel


class ChargePayload(BaseModel):
    customer_id: str
    amount_cents: int


class ChargeResult(BaseModel):
    transaction_id: str
    status: str
    net_amount_cents: int
