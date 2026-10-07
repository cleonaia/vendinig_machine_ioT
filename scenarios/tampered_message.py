import time
from decimal import Decimal

from app.domain.errors import DomainError
from app.main import create_app
from app.security.hmac_signing import build_payload, sign_message


def run() -> dict:
    app = create_app()
    service = app.state.vending_service
    tx = service.create_transaction(Decimal('1.50'))
    nonce = 'scenario-tampered'
    issued_at = int(time.time())
    payload = build_payload(tx.transaction_id, '1.50', nonce, issued_at)
    signature = sign_message('invalid-secret', payload)
    try:
        service.authorize_payment(tx.transaction_id, Decimal('1.50'), nonce, issued_at, signature)
    except DomainError as err:
        return {'scenario': 'tampered_message', 'status': 'blocked', 'reason': err.code}
    return {'scenario': 'tampered_message', 'status': 'unexpected'}
