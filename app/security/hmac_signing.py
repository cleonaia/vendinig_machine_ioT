import hashlib
import hmac


def build_payload(transaction_id: str, amount: str, nonce: str, issued_at: int) -> str:
    return f"{transaction_id}|{amount}|{nonce}|{issued_at}"


def sign_message(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_message(secret: str, payload: str, signature: str) -> bool:
    expected = sign_message(secret, payload)
    return hmac.compare_digest(expected, signature)
