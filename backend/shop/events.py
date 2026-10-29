"""Idempotent consumers shared by local execution and the three Lambdas."""

import logging
from collections.abc import Callable

from sqlalchemy import select

from shop.domain import EventType, OrderStatus
from shop.models import Event, Order, Receipt
from shop.orders import append_event

logger = logging.getLogger(__name__)
ROUTES = {
    "packing": (EventType.ORDER_CREATED,),
    "shipping": (EventType.ORDER_PACKED,),
    "notification": (EventType.ORDER_CREATED, EventType.ORDER_SHIPPED),
}
TRANSITIONS = {
    "packing": (OrderStatus.CONFIRMED, OrderStatus.PACKED, EventType.ORDER_PACKED),
    "shipping": (OrderStatus.PACKED, OrderStatus.SHIPPED, EventType.ORDER_SHIPPED),
}


def event_envelope(event: Event) -> dict:
    return {
        "schema_version": 1,
        "event_id": event.id,
        "type": event.type,
        "order_id": event.order_id,
        "occurred_at": event.created_at.isoformat(),
        "payload": event.payload,
    }


def process_event(session, consumer: str, message: dict, send_email: Callable) -> None:
    if consumer not in ROUTES or message.get("schema_version") != 1:
        raise ValueError("Unknown consumer or unsupported event schema")
    event = session.get(Event, message["event_id"])
    if not event or event.type not in ROUTES[consumer] or message.get("type") != event.type:
        raise ValueError("Event does not match the expected durable event")
    if message.get("order_id") != event.order_id:
        raise ValueError("Order does not match durable event")
    order = session.scalar(select(Order).where(Order.id == event.order_id).with_for_update())
    # Lock the order before checking the receipt, serializing duplicate deliveries.
    if session.get(Receipt, (consumer, event.id)):
        return
    if consumer == "notification":
        # SES and SQL cannot commit atomically. A crash after SES can duplicate an email.
        # Use the durable event: confirmation can arrive after the order has shipped.
        send_email(order, EventType(event.type))
    else:
        expected, target, outgoing = TRANSITIONS[consumer]
        if order.status != expected:
            raise ValueError(f"Unexpected transition: {order.status} -> {target}")
        order.status = target.value
        append_event(session, order, outgoing)
    session.add(Receipt(consumer=consumer, event_id=event.id))
    logger.info("event_processed consumer=%s event_id=%s order_id=%s", consumer, event.id, order.id)
