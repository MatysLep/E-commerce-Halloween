from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from shop.auth import authenticate
from shop.config import Settings


@pytest.fixture
def identity(monkeypatch):
    settings = Settings(
        environment="aws",
        user_pool_id="eu-west-3_test",
        client_id="web-client",
        db_secret_arn="secret",
        db_host="db.example.com",
        db_ca_bundle="ca.pem",
    )
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private_key.public_key())
    )
    monkeypatch.setattr("shop.auth.jwks_client", lambda _: jwks)
    attributes = {"sub": "alice", "email": "alice@example.com", "email_verified": "true"}
    client = SimpleNamespace(
        get_user=lambda **_: {
            "UserAttributes": [{"Name": key, "Value": value} for key, value in attributes.items()],
        }
    )
    monkeypatch.setattr("shop.auth.aws_client", lambda *_: client)
    claims = {
        "sub": "alice",
        "iss": "https://cognito-idp.eu-west-3.amazonaws.com/eu-west-3_test",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "client_id": "web-client",
        "token_use": "access",
        "scope": "openid email aws.cognito.signin.user.admin",
    }
    return settings, private_key, claims, attributes


def test_valid_signed_access_token_uses_verified_email(identity):
    settings, key, claims, _ = identity
    customer = authenticate(settings, f"Bearer {jwt.encode(claims, key, algorithm='RS256')}")
    assert customer.id == "alice"
    assert customer.email == "alice@example.com"


@pytest.mark.parametrize(
    "override",
    [
        {"token_use": "id"},
        {"client_id": "another-client"},
        {"iss": "https://attacker.example"},
        {"scope": "openid"},
        {"exp": 1},
        {"sub": "bob"},
    ],
)
def test_invalid_claims_rejected(identity, override):
    settings, key, claims, _ = identity
    token = jwt.encode({**claims, **override}, key, algorithm="RS256")
    with pytest.raises(HTTPException) as error:
        authenticate(settings, f"Bearer {token}")
    assert error.value.status_code == 401


def test_unsigned_or_wrongly_signed_tokens_rejected(identity):
    settings, _, claims, _ = identity
    token = jwt.encode(claims, "x" * 32, algorithm="HS256")
    with pytest.raises(HTTPException) as error:
        authenticate(settings, f"Bearer {token}")
    assert error.value.status_code == 401


def test_unverified_email_rejected(identity):
    settings, key, claims, attributes = identity
    attributes["email_verified"] = "false"
    with pytest.raises(HTTPException):
        authenticate(settings, f"Bearer {jwt.encode(claims, key, algorithm='RS256')}")


def test_local_demo_token_never_works_in_aws(identity):
    settings, *_ = identity
    with pytest.raises(HTTPException):
        authenticate(settings, "Bearer local-demo")


def test_aws_cannot_use_local_database_defaults():
    with pytest.raises(ValueError):
        Settings(environment="aws")
