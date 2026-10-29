"""Email content, safe HTML interpolation and useful text fallbacks."""

from types import SimpleNamespace

import pytest
from shop.domain import EventType
from shop.emails import money, render_order_email


@pytest.fixture
def order():
    return SimpleNamespace(
        id="c48b919c-93bc-4f77-bb44-1d4c348d83fc",
        total_cents=3670,
        lines=[
            SimpleNamespace(product_name="La citrouille", quantity=1, unit_price_cents=1890),
            SimpleNamespace(product_name="Les bonbons", quantity=2, unit_price_cents=890),
        ],
    )


@pytest.mark.parametrize(
    "event, subject, badge",
    [
        (EventType.ORDER_CREATED, "confirmée", "COMMANDE CONFIRMÉE"),
        (EventType.ORDER_SHIPPED, "expédiée", "COMMANDE EXPÉDIÉE"),
    ],
)
def test_emails_include_the_purchase_and_correct_event(order, event, subject, badge):
    mail = render_order_email(order, event, "https://shop.example.com/")
    assert subject in mail.subject
    assert badge in mail.html
    assert "La citrouille" in mail.html and "Les bonbons" in mail.html
    assert "17,80\u00a0€" in mail.html
    assert "36,70\u00a0€" in mail.html and "36,70\u00a0€" in mail.text
    assert "2 × Les bonbons" in mail.text
    assert order.id in mail.html and order.id in mail.text
    assert 'href="https://shop.example.com/orders.html"' in mail.html
    assert "https://shop.example.com/orders.html" in mail.text
    assert "aucun paiement ni envoi physique" in mail.text
    assert "Aucun paiement ni envoi physique" in mail.html
    assert "<script" not in mail.html
    assert "max-width:620px" in mail.html


def test_html_does_not_interpret_product_or_order_content(order):
    order.lines[0].product_name = '<img src=x onerror="alert(1)"> & potion'
    order.id = '<script>alert("order")</script>'
    mail = render_order_email(order, EventType.ORDER_CREATED)
    assert "<img src=x" not in mail.html
    assert "<script>" not in mail.html
    assert "&lt;img" in mail.html and "&amp; potion" in mail.html
    assert "&lt;script&gt;" in mail.html


@pytest.mark.parametrize(
    "url",
    [
        "http://shop.test",
        "javascript:alert(1)",
        "https://u:p@shop.test",
        "https://shop.test/?token=secret",
    ],
)
def test_unsafe_or_credential_bearing_links_are_rejected(order, url):
    with pytest.raises(ValueError):
        render_order_email(order, EventType.ORDER_CREATED, url)


def test_unconfigured_link_is_omitted(order):
    mail = render_order_email(order, EventType.ORDER_CREATED)
    assert 'href="' not in mail.html


def test_packed_event_does_not_generate_an_email(order):
    with pytest.raises(ValueError):
        render_order_email(order, EventType.ORDER_PACKED)


def test_amounts_are_formatted_without_rounding():
    assert money(129999) == "1\u202f299,99\u00a0€"
