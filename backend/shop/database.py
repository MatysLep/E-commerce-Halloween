"""Database factory. AWS credentials are refreshed when a new connection opens."""

import json
from functools import lru_cache

import boto3
import psycopg
from botocore.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from shop.config import Settings, get_settings


def aws_client(service: str, settings: Settings):
    return boto3.client(
        service,
        region_name=settings.region,
        config=Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 2}),
    )


def create_database(settings: Settings):
    if settings.environment == "aws":
        secrets = aws_client("secretsmanager", settings)

        def connect():
            secret = json.loads(
                secrets.get_secret_value(SecretId=settings.db_secret_arn)["SecretString"]
            )
            return psycopg.connect(
                host=settings.db_host,
                dbname=settings.db_name,
                user=secret["username"],
                password=secret["password"],
                sslmode="verify-full",
                sslrootcert=settings.db_ca_bundle,
                connect_timeout=5,
                options="-c statement_timeout=15000 -c lock_timeout=5000",
            )

        engine = create_engine(
            "postgresql+psycopg://",
            creator=connect,
            pool_size=2,
            max_overflow=0,
            pool_pre_ping=True,
            pool_recycle=300,
        )
    else:
        options = (
            {"check_same_thread": False, "timeout": 15} if "sqlite" in settings.database_url else {}
        )
        engine = create_engine(settings.database_url, connect_args=options, pool_pre_ping=True)
        if engine.dialect.name == "sqlite":

            @event.listens_for(engine, "connect")
            def sqlite_constraints(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")

    return engine


@lru_cache
def session_factory():
    return sessionmaker(create_database(get_settings()), expire_on_commit=False)
