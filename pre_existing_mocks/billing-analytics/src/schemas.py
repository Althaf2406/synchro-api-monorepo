"""
pre_existing_mocks/billing-analytics/src/schemas.py
Downstream Repo 2 DTO schema for settlement ledger records derived from ChargeResponse.
"""

from pydantic import BaseModel


class SettlementEventRecord(BaseModel):
    transaction_id: str
    customer_id: str
    status: str
    amount_cents: int
