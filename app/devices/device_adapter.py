from decimal import Decimal

from app.devices.payment_reader_simulator import PaymentReaderSimulator
from app.services.vending_service import VendingService


class DeviceAdapter:
    def __init__(self, vending_service: VendingService, payment_reader: PaymentReaderSimulator) -> None:
        self.vending_service = vending_service
        self.payment_reader = payment_reader

    def authorize(self, transaction_id: str, amount: Decimal) -> None:
        payload = self.payment_reader.build_authorization(transaction_id, amount)
        self.vending_service.authorize_payment(
            transaction_id=transaction_id,
            amount=amount,
            nonce=payload["nonce"],
            issued_at=payload["issued_at"],
            signature=payload["signature"],
        )
