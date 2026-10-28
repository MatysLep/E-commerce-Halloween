"""SQS entry point: acknowledge successful records and retry only failed records."""

import json
import logging

from shop.config import get_settings
from shop.database import aws_client, session_factory
from shop.events import process_event

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def send_confirmation(order):
    settings = get_settings()
    if not settings.sender_email:
        raise ValueError("SES_SENDER_EMAIL is required")
    aws_client("ses", settings).send_email(
        Source=settings.sender_email,
        Destination={"ToAddresses": [order.customer_email]},
        Message={
            "Subject": {"Data": "Votre commande Halloween est confirmée", "Charset": "UTF-8"},
            "Body": {
                "Text": {
                    "Data": (
                        f"Merci ! Votre commande {order.id} est confirmée.\n"
                        f"Montant : {order.total_cents / 100:.2f} EUR.\n"
                        "L’emballage et l’expédition de cette démonstration sont simulés."
                    ),
                    "Charset": "UTF-8",
                }
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
        except Exception:
            # Never log the raw body, tokens or customer email.
            logger.error("record_failed consumer=%s message_id=%s", consumer, record["messageId"])
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}


def handler(event, context):
    logging.getLogger("shop.events").setLevel(logging.INFO)
    return handle_batch(event, session_factory(), get_settings().consumer, send_confirmation)
