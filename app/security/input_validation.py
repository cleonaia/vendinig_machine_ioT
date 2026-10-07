from decimal import Decimal

from app.domain.errors import DomainError


def ensure_positive_amount(amount: Decimal) -> None:
    if amount <= Decimal("0"):
        raise DomainError("El importe debe ser mayor a cero", code="invalid_amount", status_code=422)


def ensure_product_id(product_id: str) -> None:
    if not product_id or not product_id.replace("-", "").replace("_", "").isalnum():
        raise DomainError("Producto inválido", code="invalid_product", status_code=422)
