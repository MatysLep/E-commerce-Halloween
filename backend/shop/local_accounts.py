"""Persistent local accounts with salted password hashes and opaque expiring sessions."""

import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from shop.domain import Customer
from shop.models import LocalAccount, LocalSession


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def register(factory, email, password):
    salt = secrets.token_hex(16)
    account = LocalAccount(email=email, password_hash=f"{salt}:{password_hash(password, salt)}")
    try:
        with factory.begin() as session:
            session.add(account)
    except IntegrityError as error:
        raise HTTPException(409, "Un compte existe déjà avec cette adresse e-mail.") from error


def sign_in(factory, email, password):
    with factory.begin() as session:
        account = session.scalar(select(LocalAccount).where(LocalAccount.email == email))
        salt = account.password_hash.split(":")[0] if account else "0" * 32
        candidate = password_hash(password, salt)
        if not account or not hmac.compare_digest(candidate, account.password_hash.split(":")[1]):
            raise HTTPException(401, "Adresse e-mail ou mot de passe incorrect.")
        token = secrets.token_urlsafe(32)
        session.execute(delete(LocalSession).where(LocalSession.expires_at <= int(time.time())))
        session.add(
            LocalSession(
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                account_id=account.id,
                expires_at=int(time.time()) + 3600,
            )
        )
        return {"access_token": token, "expires_in": 3600}


def authenticate_local(factory, token):
    with factory() as session:
        row = session.get(LocalSession, hashlib.sha256(token.encode()).hexdigest())
        if row and row.expires_at > time.time():
            account = session.get(LocalAccount, row.account_id)
            if account:
                return Customer(account.id, account.email)
    raise HTTPException(401, "Session invalide ou expirée. Reconnectez-vous.")


def sign_out(factory, token):
    with factory.begin() as session:
        session.execute(
            delete(LocalSession).where(
                LocalSession.token_hash == hashlib.sha256(token.encode()).hexdigest()
            )
        )
