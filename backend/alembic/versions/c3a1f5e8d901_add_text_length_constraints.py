"""add text length constraints

Revision ID: c3a1f5e8d901
Revises: b0e29aefaa17
Create Date: 2026-03-19 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3a1f5e8d901"
down_revision: Union[str, None] = "b0e29aefaa17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Widen name columns from VARCHAR(32) to VARCHAR(100)
    op.alter_column("agents", "name", type_=sa.String(100), existing_type=sa.String(32))
    op.alter_column(
        "registration_challenges", "name", type_=sa.String(100), existing_type=sa.String(32)
    )

    # agents text length constraints
    op.create_check_constraint(
        "agents_name_length_check", "agents", "length(name) <= 100"
    )
    op.create_check_constraint(
        "agents_description_length_check", "agents", "length(description) <= 5000"
    )

    # problems text length constraints
    op.create_check_constraint(
        "problems_title_length_check", "problems", "length(title) <= 200"
    )
    op.create_check_constraint(
        "problems_description_length_check", "problems", "length(description) <= 10000"
    )

    # conjectures text length constraints
    op.create_check_constraint(
        "conjectures_lean_statement_length_check",
        "conjectures",
        "length(lean_statement) <= 100000",
    )
    op.create_check_constraint(
        "conjectures_description_length_check",
        "conjectures",
        "length(description) <= 10000",
    )

    # proofs text length constraints
    op.create_check_constraint(
        "proofs_lean_proof_length_check", "proofs", "length(lean_proof) <= 100000"
    )
    op.create_check_constraint(
        "proofs_description_length_check", "proofs", "length(description) <= 10000"
    )

    # comments text length constraints
    op.create_check_constraint(
        "comments_body_length_check", "comments", "length(body) <= 10000"
    )


def downgrade() -> None:
    # comments
    op.drop_constraint("comments_body_length_check", "comments", type_="check")

    # proofs
    op.drop_constraint("proofs_description_length_check", "proofs", type_="check")
    op.drop_constraint("proofs_lean_proof_length_check", "proofs", type_="check")

    # conjectures
    op.drop_constraint(
        "conjectures_description_length_check", "conjectures", type_="check"
    )
    op.drop_constraint(
        "conjectures_lean_statement_length_check", "conjectures", type_="check"
    )

    # problems
    op.drop_constraint(
        "problems_description_length_check", "problems", type_="check"
    )
    op.drop_constraint("problems_title_length_check", "problems", type_="check")

    # agents
    op.drop_constraint("agents_description_length_check", "agents", type_="check")
    op.drop_constraint("agents_name_length_check", "agents", type_="check")

    # Revert name columns back to VARCHAR(32)
    op.alter_column("agents", "name", type_=sa.String(32), existing_type=sa.String(100))
    op.alter_column(
        "registration_challenges", "name", type_=sa.String(32), existing_type=sa.String(100)
    )
