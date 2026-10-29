"""SQS entry point: acknowledge successful records and retry only failed records."""

import json
import logging

from botocore.exceptions import ClientError

from shop.config import get_settings
from shop.database import aws_client, session_factory
from shop.domain import EventType
from shop.emails import render_order_email
from shop.events import process_event

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def send_notification(order, event_type: EventType):
    settings = get_settings()
    if not settings.sender_email:
        raise ValueError("SES_SENDER_EMAIL is required")
    content = render_order_email(order, event_type, settings.site_url)
    aws_client("ses", settings).send_email(
        Source=f"Minuit <{settings.sender_email}>",
        Destination={"ToAddresses": [order.customer_email]},
        Message={
            "Subject": {"Data": content.subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": content.text, "Charset": "UTF-8"},
                "Html": {"Data": content.html, "Charset": "UTF-8"},
            },
        },
    )


def handle_batch(event, factory, consumer, sender):
    failures = []
    for record in event["Records"]:
        try:
            message = json.loads(record["body"])
            with factory.begin() as session:
                process_event(session, consumer, message, sender)
        except Exception as error:
            # Never log the raw body, tokens or customer email.
            code = (
                error.response.get("Error", {}).get("Code", "Unknown")
                if isinstance(error, ClientError)
                else "Unknown"
            )
            logger.error(
                "record_failed consumer=%s message_id=%s error_type=%s error_code=%s",
                consumer,
                record["messageId"],
                type(error).__name__,
                code,
            )
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}


def handler(event, context):
    logging.getLogger("shop.events").setLevel(logging.INFO)
    return handle_batch(event, session_factory(), get_settings().consumer, send_notification)
