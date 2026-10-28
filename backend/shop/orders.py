"""Order use cases and their transaction boundaries."""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from shop.domain import (
    BusinessError,
    Customer,
    EventType,
    OrderItem,
    normalize_items,
    request_fingerprint,
)
from shop.models import Event, Order, OrderLine, Outbox, Product, new_id


def append_event(session, order: Order, event_type: EventType) -> Event:
    event = Event(
        id=new_id(),
        order_id=order.id,
        type=event_type.value,
        payload={"order_id": order.id, "status": order.status, "total_cents": order.total_cents},
    )
    session.add(event)
    session.flush()
    session.add(Outbox(event_id=event.id))
    return event


def existing_order(session, customer_id: str, key: str):
    return session.scalar(
        select(Order).where(
            Order.customer_id == customer_id,
            Order.idempotency_key == key,
        )
    )


def check_replay(order: Order, fingerprint: str) -> Order:
    if order.fingerprint != fingerprint:
        raise BusinessError("Cette clé de commande a déjà été utilisée pour un autre panier.")
    return order


def create_order(factory, customer: Customer, items: list[OrderItem], key: str) -> Order:
    normalized = normalize_items(items)
    fingerprint = request_fingerprint(normalized)
    try:
        with factory.begin() as session:
            previous = existing_order(session, customer.id, key)
            if previous:
                return check_replay(previous, fingerprint)
            # Reserve the unique key before touching stock. A concurrent replay waits here.
            order = Order(
                id=new_id(),
                customer_id=customer.id,
                customer_email=customer.email,
                idempotency_key=key,
                fingerprint=fingerprint,
                total_cents=1,
                status="CONFIRMED",
                lines=[],
            )
            session.add(order)
            session.flush()
            total = 0
            # Consistent lock order avoids deadlocks when carts contain the same products.
            for item in normalized:
                product = session.scalar(
                    select(Product).where(Product.id == item.product_id).with_for_update()
                )
                if not product:
                    raise BusinessError("Un produit du panier n’existe plus.", 404)
                changed = session.execute(
                    update(Product)
                    .where(
                        Product.id == item.product_id,
                        Product.stock >= item.quantity,
                    )
                    .values(stock=Product.stock - item.quantity)
                )
                if changed.rowcount != 1:
                    raise BusinessError(f"Stock insuffisant pour {product.name}.")
                order.lines.append(
                    OrderLine(
                        product_id=product.id,
                        product_name=product.name,
                        quantity=item.quantity,
                        unit_price_cents=product.price_cents,
                    )
                )
                total += product.price_cents * item.quantity
            order.total_cents = total
            append_event(session, order, EventType.ORDER_CREATED)
        return order
    except IntegrityError:
        # The losing transaction was rolled back, including any stock changes.
        with factory() as session:
            previous = existing_order(session, customer.id, key)
            if previous:
                return check_replay(previous, fingerprint)
        raise


def get_order(session, order_id: str, customer_id: str) -> Order:
    order = session.scalar(
        select(Order).where(
            Order.id == order_id,
            Order.customer_id == customer_id,
        )
    )
    if not order:
        raise BusinessError("Commande introuvable.", 404)
    return order


def serialize_order(order: Order) -> dict:
    return {
        "id": order.id,
        "status": order.status,
        "total_cents": order.total_cents,
        "created_at": order.created_at.isoformat(),
        "lines": [
            {
                "product_id": line.product_id,
                "name": line.product_name,
                "quantity": line.quantity,
                "unit_price_cents": line.unit_price_cents,
            }
            for line in order.lines
        ],
    }
