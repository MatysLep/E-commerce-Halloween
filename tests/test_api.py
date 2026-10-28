from shop.domain import Customer, OrderItem
from shop.orders import create_order

BODY = {"items": [{"product_id": "citrouille", "quantity": 1}]}


def test_catalogue_and_health_are_public(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.get("/api/products")
    assert response.status_code == 200
    assert len(response.json()) == 12
    assert response.headers["cache-control"] == "no-store"


def test_authentication_required_for_orders(client):
    assert client.post("/api/orders", json=BODY).status_code == 401
    assert client.get("/api/orders").status_code == 401


def test_checkout_and_audit_history(client, headers):
    response = client.post("/api/orders", json=BODY, headers=headers)
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "CONFIRMED"
    assert order["total_cents"] == 1890
    assert client.post("/api/orders", json=BODY, headers=headers).json()["id"] == order["id"]
    detail = client.get(f"/api/orders/{order['id']}", headers=headers).json()
    assert detail["history"][0]["type"] == "CommandeCreee"
    assert len(client.get("/api/orders", headers=headers).json()) == 1
    assert "customer_email" not in detail


def test_cannot_read_another_customers_order(client, factory, headers):
    other = create_order(
        factory, Customer("other", "other@example.com"), [OrderItem("bonbons", 1)], "other-key"
    )
    assert client.get(f"/api/orders/{other.id}", headers=headers).status_code == 404
    assert client.get("/api/orders", headers=headers).json() == []


def test_client_cannot_set_price_status_or_email(client, headers):
    for field in ["price_cents", "status", "customer_email", "customer_id"]:
        assert (
            client.post("/api/orders", json={**BODY, field: "forged"}, headers=headers).status_code
            == 422
        )
    invalid_item = {"items": [{**BODY["items"][0], "price_cents": 1}]}
    assert client.post("/api/orders", json=invalid_item, headers=headers).status_code == 422


def test_idempotency_and_cart_validation(client, headers):
    no_key = {"Authorization": headers["Authorization"]}
    assert client.post("/api/orders", json=BODY, headers=no_key).status_code == 422
    for body in [{"items": []}, {"items": [{"product_id": "citrouille", "quantity": True}]}]:
        assert client.post("/api/orders", json=body, headers=headers).status_code == 422
    assert client.get("/api/orders?limit=1000", headers=headers).status_code == 422
