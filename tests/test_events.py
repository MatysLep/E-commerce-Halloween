import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace

import pytest
from shop.domain import Customer, OrderItem
from shop.events import event_envelope, process_event
from shop.handlers import handle_batch
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
        assert session.scalar(select(func.count()).select_from(Receipt)) == 3
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
    result = handle_batch(event, factory, "notification", lambda order: sent.append(order.id))
    assert result == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert len(sent) == 1
    handle_batch(event, factory, "notification", lambda order: sent.append(order.id))
    assert len(sent) == 1


def test_failed_notification_does_not_record_success(factory):
    _, message = initial_event(factory)

    def offline(_):
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
