"""scope conversation session uniqueness per user

Revision ID: 7bb3ea4a6db1
Revises: 414b8931d2bf
Create Date: 2026-02-10 19:10:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7bb3ea4a6db1"
down_revision: Union[str, None] = "414b8931d2bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(
        index.get("name") == index_name for index in inspector.get_indexes(table_name)
    )


def _unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def upgrade() -> None:
    index_name = op.f("ix_conversations_session_id")
    constraint_name = "uq_conversations_user_id_session_id"

    if _index_exists("conversations", index_name):
        op.drop_index(index_name, table_name="conversations")

    # Be tolerant of partially migrated databases where this constraint already exists.
    if not _unique_constraint_exists("conversations", constraint_name):
        op.create_unique_constraint(
            constraint_name,
            "conversations",
            ["user_id", "session_id"],
        )

    if not _index_exists("conversations", index_name):
        op.create_index(
            index_name,
            "conversations",
            ["session_id"],
            unique=False,
        )


def downgrade() -> None:
    index_name = op.f("ix_conversations_session_id")
    constraint_name = "uq_conversations_user_id_session_id"

    if _index_exists("conversations", index_name):
        op.drop_index(index_name, table_name="conversations")

    if _unique_constraint_exists("conversations", constraint_name):
        op.drop_constraint(
            constraint_name,
            "conversations",
            type_="unique",
        )

    if not _index_exists("conversations", index_name):
        op.create_index(
            index_name,
            "conversations",
            ["session_id"],
            unique=True,
        )
