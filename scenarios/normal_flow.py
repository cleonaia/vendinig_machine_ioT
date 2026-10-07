import time
from decimal import Decimal

from app.main import create_app
from app.security.hmac_signing import build_payload, sign_message


def run() -> dict:
    app = create_app()
    service = app.state.vending_service
    tx = service.create_transaction(Decimal('1.50'))
    nonce = 'scenario-normal'
    issued_at = int(time.time())
    payload = build_payload(tx.transaction_id, '1.50', nonce, issued_at)
    signature = sign_message('change-me-local-only', payload)
    service.authorize_payment(tx.transaction_id, Decimal('1.50'), nonce, issued_at, signature)
    service.select_product(tx.transaction_id, 'A1')
    final_tx = service.dispense(tx.transaction_id)
    return {'scenario': 'normal_flow', 'state': final_tx.state.value}
