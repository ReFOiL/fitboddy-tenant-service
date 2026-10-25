"""create trainer invite codes

Revision ID: 0002_create_trainer_invite_codes
Revises: 0001_create_tenant_tables
Create Date: 2026-10-25 08:52:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_create_trainer_invite_codes"
down_revision = "0001_create_tenant_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trainer_invite_codes",
        sa.Column("trainer_user_id", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("trainer_user_id"),
        sa.UniqueConstraint("code", name="uq_trainer_invite_codes_code"),
    )


def downgrade() -> None:
    op.drop_table("trainer_invite_codes")
