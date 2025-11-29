"""Add email verification and password reset token fields

Revision ID: add_email_tokens_001
Revises: merge_crown45_heads
Create Date: 2025-11-29

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_email_tokens_001'
down_revision = 'merge_crown45_heads'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('email_verification_token', sa.String(128), nullable=True))
    op.add_column('users', sa.Column('email_verification_sent_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('password_reset_token', sa.String(128), nullable=True))
    op.add_column('users', sa.Column('password_reset_expires', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'password_reset_expires')
    op.drop_column('users', 'password_reset_token')
    op.drop_column('users', 'email_verification_sent_at')
    op.drop_column('users', 'email_verification_token')
