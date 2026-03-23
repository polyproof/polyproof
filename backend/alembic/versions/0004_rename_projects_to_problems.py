"""rename projects table to problems

Revision ID: 0004_rename_to_problems
Revises: 0003_owners_claiming
Create Date: 2026-03-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_rename_to_problems"
down_revision: str = "0003_owners_claiming"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Rename table
    op.rename_table("projects", "problems")

    # Rename the index on the table itself
    op.execute("ALTER INDEX idx_projects_created RENAME TO idx_problems_created")

    # Rename FK constraints that reference the old table name
    op.execute(
        "ALTER TABLE problems RENAME CONSTRAINT fk_projects_root_conjecture"
        " TO fk_problems_root_conjecture"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE problems RENAME CONSTRAINT fk_problems_root_conjecture"
        " TO fk_projects_root_conjecture"
    )
    op.execute("ALTER INDEX idx_problems_created RENAME TO idx_projects_created")
    op.rename_table("problems", "projects")
