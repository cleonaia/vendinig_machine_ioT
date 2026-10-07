from decimal import Decimal

from app.audit.audit_logger import AuditLogger
from app.domain import events
from app.domain.errors import DomainError
from app.domain.models import Transaction
from app.domain.states import TransactionState
from app.security.hmac_signing import build_payload, verify_message
from app.security.input_validation import ensure_positive_amount
from app.security.replay_protection import ReplayProtector


class PaymentService:
    def __init__(self, hmac_secret: str, replay_protector: ReplayProtector, audit_logger: AuditLogger) -> None:
        self.hmac_secret = hmac_secret
        self.replay_protector = replay_protector
        self.audit_logger = audit_logger

    def authorize(
        self,
        tx: Transaction,
        amount: Decimal,
        nonce: str,
        issued_at: int,
        signature: str,
        actor: str = "payment_reader_simulator",
    ) -> Transaction:
        ensure_positive_amount(amount)
        if tx.state != TransactionState.PAYMENT_PENDING:
            raise DomainError("Estado inválido para autorizar pago", code="invalid_state", status_code=409)

        payload = build_payload(tx.transaction_id, str(amount), nonce, issued_at)
        if not verify_message(self.hmac_secret, payload, signature):
            self.audit_logger.log(
                transaction_id=tx.transaction_id,
                event_type=events.SECURITY_EVENT,
                actor=actor,
                status="rejected",
                reason="Mensaje manipulado",
                metadata={"check": "hmac"},
            )
            raise DomainError("Firma inválida", code="invalid_signature", status_code=401)

        self.replay_protector.consume(nonce, issued_at)

        if Decimal(str(amount)) != tx.expected_amount:
            self.audit_logger.log(
                transaction_id=tx.transaction_id,
                event_type=events.PAYMENT_REJECTED,
                actor=actor,
                status="rejected",
                reason="Importe incorrecto",
                metadata={"expected": str(tx.expected_amount), "received": str(amount)},
            )
            raise DomainError("Importe incorrecto", code="invalid_amount", status_code=422)

        tx.paid_amount = Decimal(str(amount))
        tx.state = TransactionState.PAYMENT_AUTHORIZED
        self.audit_logger.log(
            transaction_id=tx.transaction_id,
            event_type=events.PAYMENT_AUTHORIZED,
            actor=actor,
            status="ok",
            reason="Pago autorizado",
            metadata={"amount": str(amount)},
        )
        return tx
