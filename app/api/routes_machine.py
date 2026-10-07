from fastapi import APIRouter, Request

from app.api.schemas import ApiResponse, InventoryItemResponse

router = APIRouter(prefix="/machine", tags=["machine"])


@router.get("/state", response_model=ApiResponse)
def machine_state(request: Request) -> ApiResponse:
    return ApiResponse(data={"transactions": len(request.app.state.vending_service.list_transactions())})


@router.get("/inventory", response_model=ApiResponse)
def inventory(request: Request) -> ApiResponse:
    items = [InventoryItemResponse(**item.__dict__).model_dump() for item in request.app.state.inventory_service.list_inventory()]
    return ApiResponse(data={"items": items})
