from fastapi import APIRouter, Request

from app.api.schemas import (
    ApiResponse,
    AuthorizePaymentRequest,
    CreateTransactionRequest,
    SelectProductRequest,
    TransactionResponse,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("", response_model=ApiResponse)
def create_transaction(payload: CreateTransactionRequest, request: Request) -> ApiResponse:
    tx = request.app.state.vending_service.create_transaction(payload.expected_amount)
    return ApiResponse(data={"transaction": TransactionResponse(**tx.__dict__).model_dump(mode="json")})


@router.post("/{transaction_id}/payment", response_model=ApiResponse)
def authorize_payment(transaction_id: str, payload: AuthorizePaymentRequest, request: Request) -> ApiResponse:
    tx = request.app.state.vending_service.authorize_payment(
        transaction_id=transaction_id,
        amount=payload.amount,
        nonce=payload.nonce,
        issued_at=payload.issued_at,
        signature=payload.signature,
    )
    return ApiResponse(data={"transaction": TransactionResponse(**tx.__dict__).model_dump(mode="json")})


@router.post("/{transaction_id}/select", response_model=ApiResponse)
def select_product(transaction_id: str, payload: SelectProductRequest, request: Request) -> ApiResponse:
    tx = request.app.state.vending_service.select_product(transaction_id, payload.product_id)
    return ApiResponse(data={"transaction": TransactionResponse(**tx.__dict__).model_dump(mode="json")})


@router.post("/{transaction_id}/dispense", response_model=ApiResponse)
def dispense(transaction_id: str, request: Request) -> ApiResponse:
    tx = request.app.state.vending_service.dispense(transaction_id)
    return ApiResponse(data={"transaction": TransactionResponse(**tx.__dict__).model_dump(mode="json")})


@router.post("/{transaction_id}/cancel", response_model=ApiResponse)
def cancel(transaction_id: str, request: Request) -> ApiResponse:
    tx = request.app.state.vending_service.cancel(transaction_id)
    return ApiResponse(data={"transaction": TransactionResponse(**tx.__dict__).model_dump(mode="json")})


@router.post("/{transaction_id}/timeout", response_model=ApiResponse)
def timeout(transaction_id: str, request: Request) -> ApiResponse:
    tx = request.app.state.vending_service.trigger_timeout(transaction_id)
    return ApiResponse(data={"transaction": TransactionResponse(**tx.__dict__).model_dump(mode="json")})


@router.post("/{transaction_id}/disconnect", response_model=ApiResponse)
def disconnect(transaction_id: str, request: Request) -> ApiResponse:
    tx = request.app.state.vending_service.trigger_disconnect(transaction_id)
    return ApiResponse(data={"transaction": TransactionResponse(**tx.__dict__).model_dump(mode="json")})


@router.post("/{transaction_id}/restart", response_model=ApiResponse)
def restart(transaction_id: str, request: Request) -> ApiResponse:
    tx = request.app.state.vending_service.trigger_restart(transaction_id)
    return ApiResponse(data={"transaction": TransactionResponse(**tx.__dict__).model_dump(mode="json")})


@router.post("/{transaction_id}/interrupt", response_model=ApiResponse)
def interrupt(transaction_id: str, request: Request) -> ApiResponse:
    tx = request.app.state.vending_service.trigger_dispense_interrupt(transaction_id)
    return ApiResponse(data={"transaction": TransactionResponse(**tx.__dict__).model_dump(mode="json")})
