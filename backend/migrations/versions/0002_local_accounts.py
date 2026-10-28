"""Accounts for local development; AWS continues to use Cognito."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "local_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(200), nullable=False),
    )
    op.create_table(
        "local_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("local_accounts.id"), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
    )


def downgrade():
    op.drop_table("local_sessions")
    op.drop_table("local_accounts")
