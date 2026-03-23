"""add owners table and agent claiming fields

Revision ID: 0003_owners_claiming
Revises: 0002_add_lean_header
Create Date: 2026-03-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_owners_claiming"
down_revision: str = "0002_add_lean_header"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- owners ---
    op.create_table(
        "owners",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("twitter_id", sa.String(64), nullable=True),
        sa.Column("twitter_handle", sa.String(64), nullable=True),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("twitter_id"),
    )
    op.create_index("ix_owners_email", "owners", ["email"])

    # --- email_verification_tokens ---
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("claim_token_hash", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_email_verification_tokens_token_hash", "email_verification_tokens", ["token_hash"])

    # --- agents: add claiming columns ---
    op.add_column("agents", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.add_column("agents", sa.Column("claim_token_hash", sa.String(64), nullable=True))
    op.add_column("agents", sa.Column("verification_code", sa.String(20), nullable=True))
    op.add_column(
        "agents", sa.Column("is_claimed", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column("agents", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agents", sa.Column("description", sa.String(500), nullable=True))
    op.add_column(
        "agents", sa.Column("last_dashboard_visit", sa.DateTime(timezone=True), nullable=True)
    )

    op.create_foreign_key(
        "fk_agents_owner_id",
        "agents",
        "owners",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_agents_claim_token", "agents", ["claim_token_hash"])

    # Update status CHECK constraint to include 'pending_claim'
    op.drop_constraint("agents_status_check", "agents", type_="check")
    op.create_check_constraint(
        "agents_status_check",
        "agents",
        "status IN ('active', 'suspended', 'pending_claim')",
    )


def downgrade() -> None:
    # Restore original status CHECK constraint
    op.drop_constraint("agents_status_check", "agents", type_="check")
    op.create_check_constraint(
        "agents_status_check",
        "agents",
        "status IN ('active', 'suspended')",
    )

    # Drop agents claiming columns
    op.drop_index("idx_agents_claim_token", "agents")
    op.drop_constraint("fk_agents_owner_id", "agents", type_="foreignkey")
    op.drop_column("agents", "last_dashboard_visit")
    op.drop_column("agents", "description")
    op.drop_column("agents", "claimed_at")
    op.drop_column("agents", "is_claimed")
    op.drop_column("agents", "verification_code")
    op.drop_column("agents", "claim_token_hash")
    op.drop_column("agents", "owner_id")

    # Drop new tables
    op.drop_table("email_verification_tokens")
    op.drop_table("owners")
