from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.domain.states import TransactionState


class ApiResponse(BaseModel):
    status: str = "ok"
    data: dict[str, Any]


class ErrorResponse(BaseModel):
    status: str = "error"
    error: dict[str, Any]


class CreateTransactionRequest(BaseModel):
    expected_amount: Decimal = Field(gt=0)


class AuthorizePaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    nonce: str
    issued_at: int
    signature: str


class SelectProductRequest(BaseModel):
    product_id: str


class TransactionResponse(BaseModel):
    transaction_id: str
    expected_amount: Decimal
    paid_amount: Decimal
    product_id: str | None
    state: TransactionState
    created_at: datetime
    updated_at: datetime


class InventoryItemResponse(BaseModel):
    product_id: str
    name: str
    price: Decimal
    stock: int
