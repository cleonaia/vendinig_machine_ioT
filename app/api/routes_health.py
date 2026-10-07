from fastapi import APIRouter

from app.api.schemas import ApiResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=ApiResponse)
def health() -> ApiResponse:
    return ApiResponse(data={"service": "ok"})
