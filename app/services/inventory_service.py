from decimal import Decimal

from app.domain.errors import DomainError
from app.domain.models import InventoryItem
from app.storage.interfaces import Repository


class InventoryService:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def seed_default_products(self) -> None:
        if self.repository.list_inventory():
            return
        self.repository.save_inventory_item(InventoryItem(product_id="A1", name="Agua", price=Decimal("1.50"), stock=10))
        self.repository.save_inventory_item(InventoryItem(product_id="B2", name="Snack", price=Decimal("2.20"), stock=8))

    def list_inventory(self) -> list[InventoryItem]:
        return self.repository.list_inventory()

    def get_product(self, product_id: str) -> InventoryItem:
        item = self.repository.get_inventory_item(product_id)
        if not item:
            raise DomainError("Producto no existe", code="product_not_found", status_code=404)
        return item

    def decrement_stock(self, product_id: str) -> None:
        item = self.get_product(product_id)
        if item.stock <= 0:
            raise DomainError("Producto sin stock", code="out_of_stock", status_code=409)
        item.stock -= 1
        self.repository.save_inventory_item(item)
