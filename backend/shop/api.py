"""HTTP adapter: validate input, authenticate, invoke use cases, serialize output."""

import logging
import re
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from shop.auth import authenticate
from shop.config import Settings, get_settings
from shop.database import session_factory
from shop.domain import BusinessError, Customer, OrderItem
from shop.local_accounts import register, sign_in, sign_out
from shop.models import Event, Order, Product
from shop.orders import create_order, get_order, serialize_order

logger = logging.getLogger(__name__)


class AccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=1, max_length=256)


class ItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: str = Field(min_length=1, max_length=80)
    quantity: int = Field(ge=1, le=20, strict=True)


class OrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ItemInput] = Field(min_length=1, max_length=50)


def create_app(settings: Settings | None = None, factory=None) -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    settings = settings or get_settings()
    factory = factory or session_factory()
    app = FastAPI(
        title="Halloween Shop",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    def customer(authorization: Annotated[str | None, Header()] = None):
        return authenticate(settings, authorization, factory)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        logger.info(
            "request request_id=%s method=%s status=%s",
            request_id,
            request.method,
            response.status_code,
        )
        return response

    @app.exception_handler(BusinessError)
    async def business_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=error.status_code)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        logger.error("database_unavailable")
        return JSONResponse(
            {"detail": "Service temporairement indisponible. Réessayez."}, status_code=503
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        detail = (
            "Vérifiez votre adresse e-mail et votre mot de passe (256 caractères maximum)."
            if request.url.path.startswith("/api/auth/")
            else "Données invalides. Vérifiez le panier et la clé de commande."
        )
        return JSONResponse({"detail": detail}, status_code=422)

    @app.get("/api/health")
    def health():
        with factory() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.get("/api/products")
    def products():
        with factory() as session:
            rows = session.scalars(select(Product).order_by(Product.id)).all()
            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "description": row.description,
                    "category": row.category,
                    "emoji": row.emoji,
                    "price_cents": row.price_cents,
                    "stock": row.stock,
                }
                for row in rows
            ]

    if settings.environment in {"local", "test"}:

        @app.post("/api/auth/signup", status_code=201)
        def signup(body: AccountInput):
            password = body.password
            if len(password) < 12 or not all(
                re.search(pattern, password)
                for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]")
            ):
                return JSONResponse(
                    {
                        "detail": (
                            "Choisissez 12 caractères avec majuscule, "
                            "minuscule, chiffre et symbole."
                        )
                    },
                    status_code=422,
                )
            register(factory, str(body.email).lower(), password)
            return {"confirmed": True}

        @app.post("/api/auth/signin")
        def signin(body: AccountInput):
            return sign_in(factory, str(body.email).lower(), body.password)

        @app.post("/api/auth/signout", status_code=204)
        def signout(
            user: Annotated[Customer, Depends(customer)], authorization: Annotated[str, Header()]
        ):
            sign_out(factory, authorization.removeprefix("Bearer "))

    @app.get("/api/me")
    def me(user: Annotated[Customer, Depends(customer)]):
        return {"email": user.email, "demo": settings.environment != "aws"}

    @app.post("/api/orders", status_code=201)
    def place_order(
        body: OrderInput,
        user: Annotated[Customer, Depends(customer)],
        idempotency_key: Annotated[
            str, Header(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
        ],
    ):
        items = [OrderItem(item.product_id, item.quantity) for item in body.items]
        return serialize_order(create_order(factory, user, items, idempotency_key))

    @app.get("/api/orders")
    def orders(
        user: Annotated[Customer, Depends(customer)],
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    ):
        with factory() as session:
            rows = session.scalars(
                select(Order)
                .where(Order.customer_id == user.id)
                .order_by(Order.created_at.desc(), Order.id)
                .offset(offset)
                .limit(limit)
            ).all()
            return [serialize_order(row) for row in rows]

    @app.get("/api/orders/{order_id}")
    def order_detail(order_id: str, user: Annotated[Customer, Depends(customer)]):
        with factory() as session:
            order = get_order(session, order_id, user.id)
            result = serialize_order(order)
            events = session.scalars(
                select(Event).where(Event.order_id == order.id).order_by(Event.created_at, Event.id)
            ).all()
            result["history"] = [
                {"type": event.type, "at": event.created_at.isoformat()} for event in events
            ]
            return result

    frontend = Path(__file__).resolve().parents[2] / "frontend"
    if settings.environment == "local" and frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app
