"""add report to conversations

Revision ID: c6d5e4f3a2b1
Revises: a5b4c3d2e1f0
Create Date: 2026-02-25

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c6d5e4f3a2b1"
down_revision: Union[str, None] = "a5b4c3d2e1f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("report", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "report")
