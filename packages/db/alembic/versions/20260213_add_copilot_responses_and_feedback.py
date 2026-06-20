"""add copilot_feedback (depends on 8cc4fb5a7ec2 compatibility revision)

Revision ID: a5b4c3d2e1f0
Revises: 8cc4fb5a7ec2
Create Date: 2026-02-13

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a5b4c3d2e1f0"
down_revision: Union[str, None] = "8cc4fb5a7ec2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "copilot_feedback",
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
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
            ["message_id"],
            ["conversation_messages.id"],
            name=op.f("fk_copilot_feedback_message_id_conversation_messages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_copilot_feedback_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_copilot_feedback")),
        sa.UniqueConstraint(
            "message_id",
            name=op.f("uq_copilot_feedback_message_id"),
        ),
    )
    op.create_index(
        op.f("ix_copilot_feedback_message_id"),
        "copilot_feedback",
        ["message_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_copilot_feedback_user_id"),
        "copilot_feedback",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_copilot_feedback_user_id"),
        table_name="copilot_feedback",
    )
    op.drop_index(
        op.f("ix_copilot_feedback_message_id"),
        table_name="copilot_feedback",
    )
    op.drop_table("copilot_feedback")
