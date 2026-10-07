from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes_audit import router as audit_router
from app.api.routes_health import router as health_router
from app.api.routes_machine import router as machine_router
from app.api.routes_transactions import router as transactions_router
from app.config import settings
from app.audit.audit_logger import AuditLogger
from app.audit.event_store import EventStore
from app.domain.errors import DomainError
from app.security.replay_protection import ReplayProtector
from app.services.dispensing_service import DispensingService
from app.services.inventory_service import InventoryService
from app.services.payment_service import PaymentService
from app.services.recovery_service import RecoveryService
from app.services.vending_service import VendingService
from app.storage.database import create_connection
from app.storage.memory_repository import MemoryRepository
from app.storage.sqlite_repository import SQLiteRepository


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    if settings.storage_backend == "sqlite":
        repository = SQLiteRepository(create_connection(settings.sqlite_path))
    else:
        repository = MemoryRepository()

    event_store = EventStore(repository)
    audit_logger = AuditLogger(event_store)
    inventory_service = InventoryService(repository)
    inventory_service.seed_default_products()
    payment_service = PaymentService(settings.hmac_secret, ReplayProtector(settings.nonce_ttl_seconds), audit_logger)
    dispensing_service = DispensingService(inventory_service, audit_logger)
    recovery_service = RecoveryService(audit_logger)
    vending_service = VendingService(
        repository=repository,
        inventory_service=inventory_service,
        payment_service=payment_service,
        dispensing_service=dispensing_service,
        recovery_service=recovery_service,
        audit_logger=audit_logger,
    )

    app.state.repository = repository
    app.state.audit_logger = audit_logger
    app.state.inventory_service = inventory_service
    app.state.vending_service = vending_service

    app.include_router(health_router)
    app.include_router(machine_router)
    app.include_router(transactions_router)
    app.include_router(audit_router)

    @app.exception_handler(DomainError)
    def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "error": {"code": exc.code, "message": exc.message}},
        )

    return app


app = create_app()
