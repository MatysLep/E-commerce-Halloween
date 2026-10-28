import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from shop.api import create_app
from shop.config import Settings
from shop.database import create_database
from shop.models import Base
from shop.seed import seed
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture(params=["sqlite", "postgres"])
def factory(request, tmp_path):
    admin_engine = None
    schema = None
    if request.param == "postgres":
        url = os.getenv("TEST_DATABASE_URL")
        if not url:
            pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
        schema = f"test_{uuid4().hex}"
        admin_engine = create_engine(url)
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_database(
            Settings(environment="test", database_url=f"sqlite:///{tmp_path}/test.db")
        )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as session:
        seed(session)
    yield sessions
    engine.dispose()
    if admin_engine:
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def client(factory):
    with TestClient(create_app(Settings(environment="test"), factory)) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"Authorization": "Bearer local-demo", "Idempotency-Key": "test-order-1234"}
