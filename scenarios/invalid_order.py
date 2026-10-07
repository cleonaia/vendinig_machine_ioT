from decimal import Decimal

from app.domain.errors import DomainError
from app.main import create_app


def run() -> dict:
    app = create_app()
    service = app.state.vending_service
    tx = service.create_transaction(Decimal('1.50'))
    try:
        service.select_product(tx.transaction_id, 'A1')
    except DomainError as err:
        return {'scenario': 'invalid_order', 'status': 'blocked', 'reason': err.code}
    return {'scenario': 'invalid_order', 'status': 'unexpected'}
