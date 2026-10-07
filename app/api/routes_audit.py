from fastapi import APIRouter, Request

from app.api.schemas import ApiResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=ApiResponse)
def list_audit(request: Request) -> ApiResponse:
    events = []
    for event in request.app.state.audit_logger.list_events():
        events.append(
            {
                "timestamp": event.timestamp.isoformat(),
                "transaction_id": event.transaction_id,
                "event_type": event.event_type,
                "actor": event.actor,
                "status": event.status,
                "reason": event.reason,
                "metadata": event.metadata,
            }
        )
    return ApiResponse(data={"events": events})
