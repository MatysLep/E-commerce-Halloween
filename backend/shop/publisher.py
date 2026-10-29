"""Transactional outbox publisher with row locks, retries and bounded batches."""

import json
import logging
import signal
import time
from datetime import UTC, timedelta

from sqlalchemy import func, select

from shop.config import get_settings
from shop.database import aws_client, session_factory
from shop.events import ROUTES, event_envelope, process_event
from shop.models import Event, Outbox, utcnow

logger = logging.getLogger(__name__)


def publish_pending(factory, deliver, limit: int = 20) -> int:
    published = 0
    for _ in range(limit):
        with factory.begin() as session:
            row = session.scalar(
                select(Outbox)
                .where(
                    Outbox.published_at.is_(None),
                    Outbox.available_at <= utcnow(),
                )
                .order_by(Outbox.available_at, Outbox.event_id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                break
            event = session.get(Event, row.event_id)
            try:
                # Savepoint rolls back partial local effects while retaining retry metadata.
                with session.begin_nested():
                    deliver(session, event_envelope(event))
                row.published_at = utcnow()
                published += 1
            except Exception:
                row.attempts += 1
                row.available_at = utcnow() + timedelta(seconds=min(300, 2 ** min(row.attempts, 8)))
                logger.error("outbox_retry event_id=%s attempt=%s", row.event_id, row.attempts)
    return published


def local_delivery(session, message: dict):
    def log_email(order, event_type):
        logger.info("email_simulated order_id=%s event_type=%s", order.id, event_type)

    for consumer, event_types in ROUTES.items():
        if message["type"] in event_types:
            process_event(session, consumer, message, log_email)


def outbox_age(factory) -> float:
    with factory() as session:
        oldest = session.scalar(
            select(func.min(Event.created_at))
            .join(
                Outbox,
                Outbox.event_id == Event.id,
            )
            .where(Outbox.published_at.is_(None))
        )
    if oldest is None:
        return 0
    return max(0, (utcnow() - oldest.replace(tzinfo=UTC)).total_seconds())


def report_outbox_age(factory, cloudwatch, topic_arn):
    try:
        cloudwatch.put_metric_data(
            Namespace="HalloweenShop",
            MetricData=[
                {
                    "MetricName": "OutboxAgeSeconds",
                    "Value": outbox_age(factory),
                    "Unit": "Seconds",
                    "Dimensions": [{"Name": "Topic", "Value": topic_arn}],
                }
            ],
        )
    except Exception:
        # Monitoring must not prevent order processing. Missing metrics trigger an alarm.
        logger.error("publisher_metrics_unavailable")


def main():
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if settings.environment == "aws":
        if not settings.topic_arn:
            raise ValueError("EVENT_TOPIC_ARN is required")
        sns = aws_client("sns", settings)
        cloudwatch = aws_client("cloudwatch", settings)

        def deliver(session, message):
            sns.publish(
                TopicArn=settings.topic_arn,
                Message=json.dumps(message),
                MessageAttributes={
                    "event_type": {"DataType": "String", "StringValue": message["type"]}
                },
            )
    else:
        deliver = local_delivery
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    last_metric = 0
    while running:
        try:
            if settings.environment == "aws" and time.monotonic() - last_metric >= 30:
                report_outbox_age(session_factory(), cloudwatch, settings.topic_arn)
                last_metric = time.monotonic()
            if publish_pending(session_factory(), deliver) == 0:
                time.sleep(1)
        except Exception:
            logger.error("publisher_unavailable")
            time.sleep(5)


if __name__ == "__main__":
    main()
