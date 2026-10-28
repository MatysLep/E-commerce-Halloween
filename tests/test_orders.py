from concurrent.futures import ThreadPoolExecutor

import pytest
from shop.domain import BusinessError, Customer, OrderItem
from shop.models import Event, Order, Outbox, Product
from shop.orders import create_order
from sqlalchemy import func, select

CUSTOMER = Customer("alice", "alice@example.com")


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_order_commits_stock_lines_audit_and_outbox_together(factory):
    order = create_order(factory, CUSTOMER, [OrderItem("citrouille", 2)], "new-order")
    assert order.total_cents == 3780
    assert order.lines[0].unit_price_cents == 1890
    with factory() as session:
        assert session.get(Product, "citrouille").stock == 98
        assert count(session, Order) == count(session, Event) == count(session, Outbox) == 1


def test_insufficient_stock_rolls_back_the_whole_cart(factory):
    with factory.begin() as session:
        session.get(Product, "citrouille").stock = 0
    with pytest.raises(BusinessError, match="Stock insuffisant"):
        create_order(
            factory, CUSTOMER, [OrderItem("bonbons", 1), OrderItem("citrouille", 1)], "no-stock"
        )
    with factory() as session:
        assert session.get(Product, "bonbons").stock == 100
        assert count(session, Order) == count(session, Event) == count(session, Outbox) == 0


def test_replay_is_identical_even_after_stock_runs_out(factory):
    with factory.begin() as session:
        session.get(Product, "citrouille").stock = 1
    first = create_order(factory, CUSTOMER, [OrderItem("citrouille", 1)], "same-key")
    second = create_order(factory, CUSTOMER, [OrderItem("citrouille", 1)], "same-key")
    assert first.id == second.id
    with pytest.raises(BusinessError, match="autre panier"):
        create_order(factory, CUSTOMER, [OrderItem("bonbons", 1)], "same-key")


def test_duplicates_in_cart_are_normalized(factory):
    first = create_order(
        factory, CUSTOMER, [OrderItem("bonbons", 1), OrderItem("bonbons", 2)], "merged-key"
    )
    replay = create_order(factory, CUSTOMER, [OrderItem("bonbons", 3)], "merged-key")
    assert first.id == replay.id
    assert first.lines[0].quantity == 3


@pytest.mark.parametrize("quantity", [0, -1, 21, True, 1.5])
def test_invalid_quantities_rejected(factory, quantity):
    with pytest.raises(BusinessError):
        create_order(factory, CUSTOMER, [OrderItem("bonbons", quantity)], "bad-quantity")


def test_idempotency_is_scoped_to_customer(factory):
    first = create_order(factory, CUSTOMER, [OrderItem("bonbons", 1)], "shared-key")
    second = create_order(
        factory, Customer("bob", "bob@example.com"), [OrderItem("bonbons", 1)], "shared-key"
    )
    assert first.id != second.id


def test_concurrent_orders_cannot_oversell(factory):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Row-level concurrency must be tested on PostgreSQL")
    with factory.begin() as session:
        session.get(Product, "citrouille").stock = 3

    def order(index):
        try:
            return create_order(
                factory, CUSTOMER, [OrderItem("citrouille", 1)], f"parallel-{index}"
            ).id
        except BusinessError:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(order, range(8)))
    assert sum(item is not None for item in results) == 3
    with factory() as session:
        assert session.get(Product, "citrouille").stock == 0
        assert count(session, Order) == 3


def test_concurrent_replays_decrement_stock_once(factory):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Row-level concurrency must be tested on PostgreSQL")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda _: (
                    create_order(
                        factory,
                        CUSTOMER,
                        [OrderItem("bonbons", 1)],
                        "parallel-replay",
                    ).id
                ),
                range(8),
            )
        )
    assert len(set(results)) == 1
    with factory() as session:
        assert session.get(Product, "bonbons").stock == 99
