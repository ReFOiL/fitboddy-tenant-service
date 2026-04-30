"""create marketplace tables

Revision ID: 0001_create_tenant_tables
Revises:
Create Date: 2026-04-27 02:48:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_create_tenant_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovery_profiles",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False),
        sa.Column("looking_for_trainer", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_discovery_profiles_role", "discovery_profiles", ["role"], unique=False)
    op.create_table(
        "trainer_client_relations",
        sa.Column("relation_id", sa.String(length=36), nullable=False),
        sa.Column("trainer_user_id", sa.String(length=64), nullable=False),
        sa.Column("client_user_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("relation_id"),
        sa.UniqueConstraint("trainer_user_id", "client_user_id", name="uq_trainer_client_pair"),
    )
    op.create_index("ix_trainer_client_relations_trainer_user_id", "trainer_client_relations", ["trainer_user_id"], unique=False)
    op.create_index("ix_trainer_client_relations_client_user_id", "trainer_client_relations", ["client_user_id"], unique=False)
    op.create_index("ix_trainer_client_relations_status", "trainer_client_relations", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_trainer_client_relations_status", table_name="trainer_client_relations")
    op.drop_index("ix_trainer_client_relations_client_user_id", table_name="trainer_client_relations")
    op.drop_index("ix_trainer_client_relations_trainer_user_id", table_name="trainer_client_relations")
    op.drop_table("trainer_client_relations")
    op.drop_index("ix_discovery_profiles_role", table_name="discovery_profiles")
    op.drop_table("discovery_profiles")
