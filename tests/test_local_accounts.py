from shop.models import LocalAccount
from sqlalchemy import select

ACCOUNT = {"email": "hello@example.com", "password": "Minuit2026!Magie"}


def login(client, account=ACCOUNT):
    response = client.post("/api/auth/signin", json=account)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_local_account_lifecycle_and_order_isolation(client, factory):
    assert client.post("/api/auth/signup", json=ACCOUNT).status_code == 201
    with factory() as session:
        stored = session.scalar(select(LocalAccount))
        assert ACCOUNT["password"] not in stored.password_hash
    assert client.post("/api/auth/signup", json=ACCOUNT).status_code == 409
    assert client.post("/api/auth/signin", json={**ACCOUNT, "password": "wrong"}).status_code == 401
    headers = login(client)
    assert client.get("/api/me", headers=headers).json()["email"] == ACCOUNT["email"]
    order = client.post(
        "/api/orders",
        headers={**headers, "Idempotency-Key": "account-order"},
        json={"items": [{"product_id": "cupcakes", "quantity": 2}]},
    )
    assert order.status_code == 201
    assert order.json()["total_cents"] == 3180
    other = {**ACCOUNT, "email": "other@example.com"}
    assert client.post("/api/auth/signup", json=other).status_code == 201
    other_headers = login(client, other)
    assert client.get("/api/orders", headers=other_headers).json() == []
    assert client.get(f"/api/orders/{order.json()['id']}", headers=other_headers).status_code == 404
    assert client.post("/api/auth/signout", headers=headers).status_code == 204
    assert client.get("/api/me", headers=headers).status_code == 401


def test_local_signup_rejects_invalid_credentials(client):
    for account in [{**ACCOUNT, "email": "invalid"}, {**ACCOUNT, "password": "short"}]:
        assert client.post("/api/auth/signup", json=account).status_code == 422
