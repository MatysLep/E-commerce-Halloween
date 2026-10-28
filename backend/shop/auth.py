"""Cognito access-token verification and verified email retrieval."""

from functools import lru_cache

import jwt
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from shop.config import Settings
from shop.database import aws_client
from shop.domain import Customer


@lru_cache(maxsize=4)
def jwks_client(issuer: str):
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", timeout=5)


def authenticate(settings: Settings, authorization: str | None, factory=None) -> Customer:
    if settings.environment in {"local", "test"}:
        if authorization == "Bearer local-demo":
            return Customer("local-demo", "demo@example.com")
        if factory and authorization and authorization.startswith("Bearer "):
            from shop.local_accounts import authenticate_local

            return authenticate_local(factory, authorization.removeprefix("Bearer "))
        raise HTTPException(401, "Connectez-vous pour continuer.")
    if not settings.user_pool_id or not settings.client_id:
        raise HTTPException(503, "Authentification non configurée.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Connexion requise.")
    token = authorization.removeprefix("Bearer ")
    issuer = f"https://cognito-idp.{settings.region}.amazonaws.com/{settings.user_pool_id}"
    try:
        signing_key = jwks_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False, "require": ["exp", "iat", "sub", "iss", "client_id"]},
        )
        if claims.get("token_use") != "access" or claims["client_id"] != settings.client_id:
            raise jwt.InvalidTokenError()
        if "aws.cognito.signin.user.admin" not in claims.get("scope", "").split():
            raise jwt.InvalidTokenError()
        # GetUser also rejects revoked tokens. Email is never accepted from the order body.
        result = aws_client("cognito-idp", settings).get_user(AccessToken=token)
        attributes = {item["Name"]: item["Value"] for item in result["UserAttributes"]}
        if attributes.get("sub") != claims["sub"] or attributes.get("email_verified") != "true":
            raise jwt.InvalidTokenError()
        return Customer(claims["sub"], attributes["email"])
    except (jwt.PyJWKClientConnectionError, BotoCoreError) as error:
        raise HTTPException(
            503, "Service d’authentification temporairement indisponible."
        ) from error
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        status = 401 if code in {"NotAuthorizedException", "UserNotFoundException"} else 503
        raise HTTPException(status, "Impossible de valider la session.") from error
    except (jwt.PyJWTError, KeyError) as error:
        raise HTTPException(401, "Session invalide ou expirée.") from error
