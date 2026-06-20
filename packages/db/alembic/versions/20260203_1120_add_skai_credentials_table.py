"""add skai credentials table

Revision ID: 9b7b7d8e4f41
Revises: 3f39bcc1385a
Create Date: 2026-02-03 11:20:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9b7b7d8e4f41"
down_revision: Union[str, None] = "3f39bcc1385a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skai_credentials",
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
            comment="User owning these SKAI credentials",
        ),
        sa.Column(
            "skai_username",
            sa.String(length=255),
            nullable=True,
            comment="SKAI username used for Cognito authentication",
        ),
        sa.Column(
            "refresh_token",
            sa.Text(),
            nullable=False,
            comment="Cognito refresh token",
        ),
        sa.Column(
            "id_token",
            sa.Text(),
            nullable=True,
            comment="Cached Cognito ID token used for SKAI API requests",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="ID token expiration timestamp",
        ),
        sa.Column(
            "last_refreshed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last time the tokens were refreshed",
        ),
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_skai_credentials_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skai_credentials")),
    )
    op.create_index(
        op.f("ix_skai_credentials_user_id"),
        "skai_credentials",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_skai_credentials_user_id"), table_name="skai_credentials")
    op.drop_table("skai_credentials")
