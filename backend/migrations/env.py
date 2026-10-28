"""Alembic uses the connection supplied by the maintenance command."""

from alembic import context
from shop.models import Base

context.configure(
    connection=context.config.attributes["connection"],
    target_metadata=Base.metadata,
    compare_type=True,
)
with context.begin_transaction():
    context.run_migrations()
