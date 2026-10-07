from datetime import datetime, timezone
from decimal import Decimal
import uuid

from app.audit.audit_logger import AuditLogger
from app.domain import events
from app.domain.errors import DomainError
from app.domain.models import Transaction
from app.domain.states import TransactionState
from app.security.input_validation import ensure_product_id
from app.services.dispensing_service import DispensingService
from app.services.inventory_service import InventoryService
from app.services.payment_service import PaymentService
from app.services.recovery_service import RecoveryService
from app.storage.interfaces import Repository


class VendingService:
    def __init__(
        self,
        repository: Repository,
        inventory_service: InventoryService,
        payment_service: PaymentService,
        dispensing_service: DispensingService,
        recovery_service: RecoveryService,
        audit_logger: AuditLogger,
    ) -> None:
        self.repository = repository
        self.inventory_service = inventory_service
        self.payment_service = payment_service
        self.dispensing_service = dispensing_service
        self.recovery_service = recovery_service
        self.audit_logger = audit_logger

    def create_transaction(self, expected_amount: Decimal) -> Transaction:
        tx = Transaction(transaction_id=str(uuid.uuid4()), expected_amount=Decimal(str(expected_amount)))
        tx.state = TransactionState.PAYMENT_PENDING
        tx.updated_at = datetime.now(timezone.utc)
        self.repository.save_transaction(tx)
        self.audit_logger.log(
            transaction_id=tx.transaction_id,
            event_type=events.PAYMENT_REQUESTED,
            actor="api",
            status="ok",
            reason="Transacción iniciada",
            metadata={"expected_amount": str(expected_amount)},
        )
        return tx

    def get_transaction(self, transaction_id: str) -> Transaction:
        tx = self.repository.get_transaction(transaction_id)
        if not tx:
            raise DomainError("Transacción no encontrada", code="transaction_not_found", status_code=404)
        return tx

    def list_transactions(self) -> list[Transaction]:
        return self.repository.list_transactions()

    def authorize_payment(self, transaction_id: str, amount: Decimal, nonce: str, issued_at: int, signature: str) -> Transaction:
        tx = self.get_transaction(transaction_id)
        tx = self.payment_service.authorize(tx=tx, amount=amount, nonce=nonce, issued_at=issued_at, signature=signature)
        tx.updated_at = datetime.now(timezone.utc)
        self.repository.save_transaction(tx)
        return tx

    def select_product(self, transaction_id: str, product_id: str) -> Transaction:
        ensure_product_id(product_id)
        tx = self.get_transaction(transaction_id)
        if tx.state != TransactionState.PAYMENT_AUTHORIZED:
            self.audit_logger.log(
                transaction_id=transaction_id,
                event_type=events.SECURITY_EVENT,
                actor="api",
                status="rejected",
                reason="Orden inválida",
                metadata={"attempted": "select_product", "state": tx.state.value},
            )
            raise DomainError("Orden inválida", code="invalid_order", status_code=409)

        product = self.inventory_service.get_product(product_id)
        if product.price != tx.expected_amount:
            raise DomainError("Importe no coincide con producto", code="invalid_amount", status_code=422)

        tx.product_id = product_id
        tx.state = TransactionState.PRODUCT_SELECTED
        tx.updated_at = datetime.now(timezone.utc)
        self.repository.save_transaction(tx)
        self.audit_logger.log(
            transaction_id=transaction_id,
            event_type=events.PRODUCT_SELECTED,
            actor="api",
            status="ok",
            reason="Producto seleccionado",
            metadata={"product_id": product_id},
        )
        return tx

    def dispense(self, transaction_id: str) -> Transaction:
        tx = self.get_transaction(transaction_id)
        if tx.state != TransactionState.PRODUCT_SELECTED:
            raise DomainError("Pago no autorizado o flujo inválido", code="payment_not_authorized", status_code=409)
        tx = self.dispensing_service.start_dispensing(tx)
        self.repository.save_transaction(tx)
        tx = self.dispensing_service.complete_dispensing(tx)
        tx.updated_at = datetime.now(timezone.utc)
        self.repository.save_transaction(tx)
        return tx

    def cancel(self, transaction_id: str, reason: str = "cancelled") -> Transaction:
        tx = self.get_transaction(transaction_id)
        tx.state = TransactionState.CANCELLED
        tx.updated_at = datetime.now(timezone.utc)
        self.repository.save_transaction(tx)
        self.audit_logger.log(
            transaction_id=transaction_id,
            event_type=events.TRANSACTION_CANCELLED,
            actor="api",
            status="cancelled",
            reason=reason,
        )
        return tx

    def trigger_timeout(self, transaction_id: str) -> Transaction:
        tx = self.get_transaction(transaction_id)
        tx = self.recovery_service.timeout(tx)
        self.repository.save_transaction(tx)
        return tx

    def trigger_disconnect(self, transaction_id: str) -> Transaction:
        tx = self.get_transaction(transaction_id)
        tx = self.recovery_service.disconnect(tx)
        self.repository.save_transaction(tx)
        return tx

    def trigger_restart(self, transaction_id: str) -> Transaction:
        tx = self.get_transaction(transaction_id)
        tx = self.recovery_service.restart(tx)
        self.repository.save_transaction(tx)
        return tx

    def trigger_dispense_interrupt(self, transaction_id: str) -> Transaction:
        tx = self.get_transaction(transaction_id)
        tx = self.dispensing_service.interrupt(tx)
        self.repository.save_transaction(tx)
        return tx
