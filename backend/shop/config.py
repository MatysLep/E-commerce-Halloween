"""Explicit configuration; insecure development options cannot run in AWS mode."""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    environment: str = "local"
    database_url: str = "sqlite:///./halloween.db"
    region: str = "eu-west-3"
    user_pool_id: str = ""
    client_id: str = ""
    topic_arn: str = ""
    sender_email: str = ""
    db_secret_arn: str = ""
    db_host: str = ""
    db_name: str = "halloween"
    db_ca_bundle: str = ""
    consumer: str = ""

    def __post_init__(self):
        if self.environment not in {"local", "test", "aws"}:
            raise ValueError("APP_ENV must be local, test or aws")
        if self.environment == "aws":
            required = (self.db_secret_arn, self.db_host, self.db_ca_bundle)
            if not all(required):
                raise ValueError("AWS requires DB_SECRET_ARN, DB_HOST and DB_CA_BUNDLE")


@lru_cache
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("APP_ENV", "local"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./halloween.db"),
        region=os.getenv("AWS_REGION", "eu-west-3"),
        user_pool_id=os.getenv("COGNITO_USER_POOL_ID", ""),
        client_id=os.getenv("COGNITO_CLIENT_ID", ""),
        topic_arn=os.getenv("EVENT_TOPIC_ARN", ""),
        sender_email=os.getenv("SES_SENDER_EMAIL", ""),
        db_secret_arn=os.getenv("DB_SECRET_ARN", ""),
        db_host=os.getenv("DB_HOST", ""),
        db_name=os.getenv("DB_NAME", "halloween"),
        db_ca_bundle=os.getenv("DB_CA_BUNDLE", ""),
        consumer=os.getenv("CONSUMER", ""),
    )
