from decimal import Decimal

from app.main import create_app


def run() -> dict:
    app = create_app()
    service = app.state.vending_service
    tx = service.create_transaction(Decimal('1.50'))
    tx = service.trigger_restart(tx.transaction_id)
    return {'scenario': 'restart', 'state': tx.state.value}
