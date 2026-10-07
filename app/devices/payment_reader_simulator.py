import time
from decimal import Decimal
import uuid

from app.security.hmac_signing import build_payload, sign_message


class PaymentReaderSimulator:
    def __init__(self, hmac_secret: str) -> None:
        self.hmac_secret = hmac_secret

    def build_authorization(self, transaction_id: str, amount: Decimal, nonce: str | None = None, issued_at: int | None = None) -> dict:
        nonce_value = nonce or str(uuid.uuid4())
        issued = issued_at or int(time.time())
        payload = build_payload(transaction_id, str(amount), nonce_value, issued)
        signature = sign_message(self.hmac_secret, payload)
        return {"nonce": nonce_value, "issued_at": issued, "signature": signature}
