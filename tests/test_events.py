import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace

import pytest
from shop.domain import Customer, EventType, OrderItem
from shop.events import event_envelope, process_event
from shop.handlers import handle_batch, send_notification
from shop.models import Event, Order, Outbox, Receipt, utcnow
from shop.orders import create_order
from shop.publisher import local_delivery, outbox_age, publish_pending, report_outbox_age
from sqlalchemy import func, select


def initial_event(factory):
    order = create_order(
        factory, Customer("alice", "alice@example.com"), [OrderItem("bonbons", 1)], "event-key"
    )
    with factory() as session:
        event = session.scalar(select(Event).where(Event.order_id == order.id))
        return order.id, event_envelope(event)


def test_full_local_pipeline_and_replay(factory):
    order_id, message = initial_event(factory)
    assert publish_pending(factory, local_delivery) == 3
    with factory() as session:
        assert session.get(Order, order_id).status == "SHIPPED"
        assert session.scalar(select(func.count()).select_from(Event)) == 3
        assert session.scalar(select(func.count()).select_from(Receipt)) == 4
    with factory.begin() as session:
        process_event(session, "packing", message, lambda _: None)
    assert publish_pending(factory, local_delivery) == 0


def test_failed_metrics_do_not_interrupt_processing(factory):
    initial_event(factory)

    def unavailable(**_):
        raise ConnectionError("CloudWatch unavailable")

    report_outbox_age(factory, SimpleNamespace(put_metric_data=unavailable), "test-topic")
    assert publish_pending(factory, local_delivery) == 3
    assert outbox_age(factory) == 0


def test_failed_publication_stays_pending_then_recovers(factory):
    _, message = initial_event(factory)

    def offline(*_):
        raise ConnectionError("SNS unavailable")

    assert publish_pending(factory, offline) == 0
    with factory.begin() as session:
        row = session.get(Outbox, message["event_id"])
        assert row.published_at is None
        assert row.attempts == 1
        row.available_at = utcnow() - timedelta(seconds=1)
    assert publish_pending(factory, local_delivery) == 3


def test_partial_batch_response_retries_only_failed_records(factory):
    _, message = initial_event(factory)
    sent = []
    event = {
        "Records": [
            {"messageId": "ok", "body": json.dumps(message)},
            {"messageId": "bad", "body": "not-json"},
        ]
    }
    result = handle_batch(
        event,
        factory,
        "notification",
        lambda order, event_type: sent.append((order.id, event_type)),
    )
    assert result == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert len(sent) == 1
    handle_batch(
        event,
        factory,
        "notification",
        lambda order, event_type: sent.append((order.id, event_type)),
    )
    assert len(sent) == 1


def test_failed_notification_does_not_record_success(factory):
    _, message = initial_event(factory)

    def offline(*_):
        raise ConnectionError("SES unavailable")

    with pytest.raises(ConnectionError), factory.begin() as session:
        process_event(session, "notification", message, offline)
    with factory() as session:
        assert session.get(Receipt, ("notification", message["event_id"])) is None


def test_forged_event_is_rejected(factory):
    _, message = initial_event(factory)
    with pytest.raises(ValueError), factory.begin() as session:
        process_event(session, "packing", {**message, "order_id": "forged"}, lambda _: None)


def test_duplicate_consumers_create_one_transition(factory):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Row locks require PostgreSQL")
    order_id, message = initial_event(factory)

    def deliver(_):
        with factory.begin() as session:
            process_event(session, "packing", message, lambda _: None)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(deliver, range(8)))
    with factory() as session:
        assert session.get(Order, order_id).status == "PACKED"
        assert session.scalar(select(func.count()).select_from(Event)) == 2


def test_two_publishers_do_not_publish_the_same_locked_row(factory):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("SKIP LOCKED requires PostgreSQL")
    initial_event(factory)
    published = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(
            pool.map(
                lambda _: publish_pending(
                    factory, lambda session, event: published.append(event["event_id"])
                ),
                range(2),
            )
        )
    assert len(published) == 1


@pytest.mark.parametrize("reverse", [False, True])
def test_both_notifications_are_distinct_and_replays_are_ignored(factory, reverse):
    order_id, created = initial_event(factory)
    with factory.begin() as session:
        process_event(session, "packing", created, lambda *_: None)
        packed = session.scalar(
            select(Event).where(Event.order_id == order_id, Event.type == "EmballageTermine")
        )
        process_event(session, "shipping", event_envelope(packed), lambda *_: None)
    with factory() as session:
        shipped = event_envelope(
            session.scalar(
                select(Event).where(Event.order_id == order_id, Event.type == "ExpeditionTerminee")
            )
        )
    messages = [created, shipped]
    if reverse:
        messages.reverse()
    sent = []
    for message in messages + messages:
        with factory.begin() as session:
            process_event(
                session,
                "notification",
                message,
                lambda order, event_type: sent.append((order.id, event_type)),
            )
    assert sent == [(order_id, EventType(message["type"])) for message in messages]
    with factory() as session:
        receipts = session.scalars(select(Receipt).where(Receipt.consumer == "notification")).all()
        assert len(receipts) == 2


@pytest.mark.parametrize("event_type", [EventType.ORDER_CREATED, EventType.ORDER_SHIPPED])
def test_failed_notification_can_be_retried_for_each_event(factory, event_type):
    order_id, created = initial_event(factory)
    publish_pending(factory, local_delivery)
    with factory.begin() as session:
        event = session.scalar(
            select(Event).where(Event.order_id == order_id, Event.type == event_type)
        )
        message = event_envelope(event)
        session.delete(session.get(Receipt, ("notification", event.id)))

    def offline(*_):
        raise ConnectionError("SES unavailable")

    with pytest.raises(ConnectionError), factory.begin() as session:
        process_event(session, "notification", message, offline)
    sent = []
    with factory.begin() as session:
        process_event(session, "notification", message, lambda order, kind: sent.append(kind))
    assert sent == [event_type]


@pytest.mark.parametrize(
    "event_type, word",
    [
        (EventType.ORDER_CREATED, "confirmée"),
        (EventType.ORDER_SHIPPED, "expédiée"),
    ],
)
def test_ses_notification_uses_the_event_and_order_customer(monkeypatch, event_type, word):
    sent = []
    monkeypatch.setattr(
        "shop.handlers.get_settings",
        lambda: SimpleNamespace(
            sender_email="shop@example.com", site_url="https://shop.example.com"
        ),
    )
    monkeypatch.setattr(
        "shop.handlers.aws_client",
        lambda *_: SimpleNamespace(send_email=lambda **kwargs: sent.append(kwargs)),
    )
    order = SimpleNamespace(
        id="order-123",
        customer_email="customer@example.com",
        total_cents=1890,
        status="SHIPPED",
        lines=[],
    )
    send_notification(order, event_type)
    assert sent[0]["Source"] == "Minuit <shop@example.com>"
    assert sent[0]["Destination"] == {"ToAddresses": ["customer@example.com"]}
    assert word in sent[0]["Message"]["Subject"]["Data"]
    assert word in sent[0]["Message"]["Body"]["Text"]["Data"]
    assert "18,90\u00a0€" in sent[0]["Message"]["Body"]["Text"]["Data"]
    assert "minuit" in sent[0]["Message"]["Body"]["Html"]["Data"]
    assert "https://shop.example.com/orders.html" in sent[0]["Message"]["Body"]["Html"]["Data"]


def test_notification_logs_aws_error_code_without_customer_data(factory, caplog):
    from botocore.exceptions import ClientError

    _, message = initial_event(factory)

    def rejected(*_):
        raise ClientError(
            {"Error": {"Code": "MessageRejected", "Message": "private@example.com"}},
            "SendEmail",
        )

    result = handle_batch(
        {"Records": [{"messageId": "safe-message-id", "body": json.dumps(message)}]},
        factory,
        "notification",
        rejected,
    )
    assert result == {"batchItemFailures": [{"itemIdentifier": "safe-message-id"}]}
    assert "error_code=MessageRejected" in caplog.text
    assert "private@example.com" not in caplog.text
