"""Explicit maintenance commands; no migrations on HTTP requests."""

import argparse
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from shop.config import get_settings
from shop.database import create_database
from shop.models import Event, Order, Outbox, Receipt, utcnow
from shop.seed import seed


def initialize(connection):
    if connection.dialect.name == "postgresql":
        connection.execute(text("SELECT pg_advisory_xact_lock(20261028)"))
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
    with Session(bind=connection) as session:
        seed(session)
        session.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["init", "status", "replay"])
    parser.add_argument("--event-id")
    args = parser.parse_args()
    engine = create_database(get_settings())
    with engine.begin() as connection:
        if args.action == "init":
            initialize(connection)
            print("Base à jour ; catalogue prêt.")
        else:
            with Session(bind=connection) as session:
                if args.action == "replay":
                    if not args.event_id or not session.get(Event, args.event_id):
                        parser.error("replay demande un --event-id existant")
                    row = session.get(Outbox, args.event_id)
                    row.published_at = None
                    row.available_at = utcnow()
                    row.attempts = 0
                    session.flush()
                    print("Événement remis en attente ; les reçus de déduplication sont conservés.")
                else:
                    print(
                        json.dumps(
                            {
                                "orders": session.scalar(select(func.count()).select_from(Order)),
                                "events": session.scalar(select(func.count()).select_from(Event)),
                                "processed": session.scalar(
                                    select(func.count()).select_from(Receipt)
                                ),
                                "outbox_pending": session.scalar(
                                    select(func.count())
                                    .select_from(Outbox)
                                    .where(Outbox.published_at.is_(None))
                                ),
                                "oldest_pending": str(
                                    session.scalar(
                                        select(func.min(Outbox.available_at)).where(
                                            Outbox.published_at.is_(None)
                                        )
                                    )
                                ),
                            },
                            indent=2,
                        )
                    )


if __name__ == "__main__":
    main()
