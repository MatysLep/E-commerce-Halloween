"""Relational storage. Money is always represented as integer euro cents."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price_cents > 0"),
        CheckConstraint("stock >= 0"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(80))
    emoji: Mapped[str] = mapped_column(String(20))
    price_cents: Mapped[int]
    stock: Mapped[int]


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("customer_id", "idempotency_key"),
        CheckConstraint("total_cents > 0"),
        CheckConstraint("status IN ('CONFIRMED', 'PACKED', 'SHIPPED')"),
        Index("ix_orders_customer_created", "customer_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(String(160))
    customer_email: Mapped[str] = mapped_column(String(320))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="CONFIRMED")
    total_cents: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lines: Mapped[list["OrderLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (CheckConstraint("quantity > 0"), CheckConstraint("unit_price_cents > 0"))
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[int]
    unit_price_cents: Mapped[int]


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_order_created", "order_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Outbox(Base):
    __tablename__ = "outbox"
    __table_args__ = (Index("ix_outbox_pending", "published_at", "available_at"),)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), primary_key=True)
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Receipt(Base):
    __tablename__ = "receipts"
    consumer: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
