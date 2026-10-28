from shop.cli import initialize
from shop.models import Base, Product
from sqlalchemy import inspect
from sqlalchemy.orm import Session


def test_migration_from_empty_database_and_repeat_without_stock_reset(factory):
    engine = factory.kw["bind"]
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        initialize(connection)
    with factory.begin() as session:
        session.get(Product, "bonbons").stock = 7
    with engine.begin() as connection:
        initialize(connection)
        assert set(Base.metadata.tables).issubset(inspect(connection).get_table_names())
        with Session(bind=connection) as session:
            assert session.get(Product, "bonbons").stock == 7
