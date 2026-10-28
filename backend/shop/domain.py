"""Business vocabulary and validation, independent of HTTP and AWS."""

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum


class OrderStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"


class EventType(StrEnum):
    ORDER_CREATED = "CommandeCreee"
    ORDER_PACKED = "EmballageTermine"
    ORDER_SHIPPED = "ExpeditionTerminee"


class BusinessError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class Customer:
    id: str
    email: str


@dataclass(frozen=True)
class OrderItem:
    product_id: str
    quantity: int


def normalize_items(items: list[OrderItem]) -> list[OrderItem]:
    if not 1 <= len(items) <= 50:
        raise BusinessError("Le panier doit contenir entre 1 et 50 lignes.", 422)
    quantities: dict[str, int] = {}
    for item in items:
        if not item.product_id or type(item.quantity) is not int or not 1 <= item.quantity <= 20:
            raise BusinessError("Chaque quantité doit être comprise entre 1 et 20.", 422)
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
        if quantities[item.product_id] > 20:
            raise BusinessError("Maximum 20 exemplaires d’un produit par commande.", 422)
    return [OrderItem(key, value) for key, value in sorted(quantities.items())]


def request_fingerprint(items: list[OrderItem]) -> str:
    payload = [(item.product_id, item.quantity) for item in items]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()
