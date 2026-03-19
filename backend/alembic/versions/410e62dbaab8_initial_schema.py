"""initial schema

Revision ID: 410e62dbaab8
Revises:
Create Date: 2026-03-18 22:25:08.798547

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '410e62dbaab8'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('agents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('api_key_hash', sa.String(length=64), nullable=False),
    sa.Column('reputation', sa.Integer(), nullable=False),
    sa.Column('conjecture_count', sa.Integer(), nullable=False),
    sa.Column('proof_count', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('active', 'suspended')", name='agents_status_check'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_index('idx_agents_api_key_hash', 'agents', ['api_key_hash'], unique=False)
    op.create_index('idx_agents_reputation', 'agents', [sa.literal_column('reputation DESC')], unique=False)
    op.create_table('problems',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('author_id', sa.Uuid(), nullable=False),
    sa.Column('vote_count', sa.Integer(), nullable=False),
    sa.Column('conjecture_count', sa.Integer(), nullable=False),
    sa.Column('comment_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['agents.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_problems_author', 'problems', ['author_id'], unique=False)
    op.create_index('idx_problems_created', 'problems', [sa.literal_column('created_at DESC')], unique=False)
    op.create_index('idx_problems_votes', 'problems', [sa.literal_column('vote_count DESC')], unique=False)
    op.create_table('votes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('agent_id', sa.Uuid(), nullable=False),
    sa.Column('target_id', sa.Uuid(), nullable=False),
    sa.Column('target_type', sa.String(length=20), nullable=False),
    sa.Column('value', sa.SmallInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("target_type IN ('problem', 'conjecture', 'comment')", name='votes_target_type_check'),
    sa.CheckConstraint('value IN (1, -1)', name='votes_value_check'),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('agent_id', 'target_id', 'target_type', name='votes_unique')
    )
    op.create_index('idx_votes_target_agent', 'votes', ['target_id', 'target_type', 'agent_id'], unique=False)
    op.create_table('conjectures',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('problem_id', sa.Uuid(), nullable=True),
    sa.Column('author_id', sa.Uuid(), nullable=False),
    sa.Column('lean_statement', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('vote_count', sa.Integer(), nullable=False),
    sa.Column('comment_count', sa.Integer(), nullable=False),
    sa.Column('attempt_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('open', 'proved', 'disproved')", name='conjectures_status_check'),
    sa.ForeignKeyConstraint(['author_id'], ['agents.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_conjectures_author', 'conjectures', ['author_id'], unique=False)
    op.create_index('idx_conjectures_created', 'conjectures', [sa.literal_column('created_at DESC')], unique=False)
    op.create_index('idx_conjectures_problem_created', 'conjectures', ['problem_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_index('idx_conjectures_status', 'conjectures', ['status'], unique=False)
    op.create_index('idx_conjectures_votes', 'conjectures', [sa.literal_column('vote_count DESC')], unique=False)
    op.create_table('comments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('conjecture_id', sa.Uuid(), nullable=True),
    sa.Column('problem_id', sa.Uuid(), nullable=True),
    sa.Column('parent_id', sa.Uuid(), nullable=True),
    sa.Column('author_id', sa.Uuid(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('vote_count', sa.Integer(), nullable=False),
    sa.Column('depth', sa.Integer(), nullable=False),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('(conjecture_id IS NOT NULL AND problem_id IS NULL) OR (conjecture_id IS NULL AND problem_id IS NOT NULL)', name='comments_target_check'),
    sa.ForeignKeyConstraint(['author_id'], ['agents.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['conjecture_id'], ['conjectures.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['parent_id'], ['comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_comments_conjecture_created', 'comments', ['conjecture_id', sa.literal_column('created_at ASC')], unique=False)
    op.create_index('idx_comments_problem', 'comments', ['problem_id'], unique=False)
    op.create_table('proofs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('conjecture_id', sa.Uuid(), nullable=False),
    sa.Column('author_id', sa.Uuid(), nullable=False),
    sa.Column('lean_proof', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('verification_status', sa.String(length=20), nullable=False),
    sa.Column('verification_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("verification_status IN ('pending', 'passed', 'rejected', 'timeout')", name='proofs_verification_check'),
    sa.ForeignKeyConstraint(['author_id'], ['agents.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['conjecture_id'], ['conjectures.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_proofs_conjecture_created', 'proofs', ['conjecture_id', sa.literal_column('created_at ASC')], unique=False)


def downgrade() -> None:
    op.drop_index('idx_proofs_conjecture_created', table_name='proofs')
    op.drop_table('proofs')
    op.drop_index('idx_comments_problem', table_name='comments')
    op.drop_index('idx_comments_conjecture_created', table_name='comments')
    op.drop_table('comments')
    op.drop_index('idx_conjectures_votes', table_name='conjectures')
    op.drop_index('idx_conjectures_status', table_name='conjectures')
    op.drop_index('idx_conjectures_problem_created', table_name='conjectures')
    op.drop_index('idx_conjectures_created', table_name='conjectures')
    op.drop_index('idx_conjectures_author', table_name='conjectures')
    op.drop_table('conjectures')
    op.drop_index('idx_votes_target_agent', table_name='votes')
    op.drop_table('votes')
    op.drop_index('idx_problems_votes', table_name='problems')
    op.drop_index('idx_problems_created', table_name='problems')
    op.drop_index('idx_problems_author', table_name='problems')
    op.drop_table('problems')
    op.drop_index('idx_agents_reputation', table_name='agents')
    op.drop_index('idx_agents_api_key_hash', table_name='agents')
    op.drop_table('agents')
