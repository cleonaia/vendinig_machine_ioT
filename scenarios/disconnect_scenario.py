from decimal import Decimal

from app.main import create_app


def run() -> dict:
    app = create_app()
    service = app.state.vending_service
    tx = service.create_transaction(Decimal('1.50'))
    tx = service.trigger_disconnect(tx.transaction_id)
    return {'scenario': 'disconnect', 'state': tx.state.value}
