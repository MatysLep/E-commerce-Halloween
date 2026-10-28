"""Deployment-only Lambda. It is the only runtime with the RDS master secret."""

import json
import os

from psycopg import sql

from shop.cli import initialize
from shop.config import get_settings
from shop.database import aws_client, create_database


def provision_application_role(connection, credentials: dict):
    if credentials.get("username") != "halloween_app":
        raise ValueError("Unexpected application database role")
    # psycopg composes identifiers/literals safely, including password punctuation.
    with connection.connection.driver_connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = 'halloween_app'")
        if not cursor.fetchone():
            cursor.execute("CREATE ROLE halloween_app LOGIN")
        cursor.execute(
            sql.SQL("ALTER ROLE halloween_app PASSWORD {}").format(
                sql.Literal(credentials["password"]),
            )
        )
        cursor.execute("GRANT CONNECT ON DATABASE halloween TO halloween_app")
        cursor.execute("GRANT USAGE ON SCHEMA public TO halloween_app")
        cursor.execute("GRANT SELECT, INSERT ON order_lines, events, receipts TO halloween_app")
        cursor.execute("GRANT SELECT, INSERT, UPDATE ON products, orders, outbox TO halloween_app")


def handler(event, context):
    settings = get_settings()
    secret = aws_client("secretsmanager", settings).get_secret_value(
        SecretId=os.environ["APP_DB_SECRET_ARN"],
    )
    engine = create_database(settings)
    try:
        with engine.begin() as connection:
            initialize(connection)
            provision_application_role(connection, json.loads(secret["SecretString"]))
    finally:
        engine.dispose()
    return {"status": "ready"}
