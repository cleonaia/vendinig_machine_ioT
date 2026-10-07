from app.audit.audit_logger import AuditLogger
from app.domain import events
from app.domain.errors import DomainError
from app.domain.models import Transaction
from app.domain.states import TransactionState
from app.services.inventory_service import InventoryService


class DispensingService:
    def __init__(self, inventory_service: InventoryService, audit_logger: AuditLogger) -> None:
        self.inventory_service = inventory_service
        self.audit_logger = audit_logger

    def start_dispensing(self, tx: Transaction, actor: str = "actuator_simulator") -> Transaction:
        if tx.state != TransactionState.PRODUCT_SELECTED:
            raise DomainError("No se puede dispensar en este estado", code="invalid_state", status_code=409)
        tx.state = TransactionState.DISPENSING
        self.audit_logger.log(
            transaction_id=tx.transaction_id,
            event_type=events.DISPENSING_STARTED,
            actor=actor,
            status="ok",
            reason="Dispensación iniciada",
        )
        return tx

    def complete_dispensing(self, tx: Transaction, actor: str = "actuator_simulator") -> Transaction:
        if tx.state != TransactionState.DISPENSING:
            raise DomainError("Secuencia inválida de dispensación", code="invalid_order", status_code=409)
        if not tx.product_id:
            raise DomainError("Producto no seleccionado", code="invalid_order", status_code=409)

        self.inventory_service.decrement_stock(tx.product_id)
        tx.state = TransactionState.COMPLETED
        self.audit_logger.log(
            transaction_id=tx.transaction_id,
            event_type=events.DISPENSING_COMPLETED,
            actor=actor,
            status="ok",
            reason="Dispensación completada",
            metadata={"product_id": tx.product_id},
        )
        return tx

    def interrupt(self, tx: Transaction, actor: str = "actuator_simulator") -> Transaction:
        tx.state = TransactionState.ERROR
        self.audit_logger.log(
            transaction_id=tx.transaction_id,
            event_type=events.TRANSACTION_ERROR,
            actor=actor,
            status="fail_secure",
            reason="Interrupción de dispensación",
        )
        return tx
