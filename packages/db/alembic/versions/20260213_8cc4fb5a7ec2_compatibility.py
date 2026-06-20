"""compatibility revision 8cc4fb5a7ec2 (no-op)

Environments that were previously stamped at 8cc4fb5a7ec2 will have this
revision applied; the actual copilot_feedback table is created in the
next revision (add_copilot_responses_and_feedback).

Revision ID: 8cc4fb5a7ec2
Revises: 7bb3ea4a6db1
Create Date: 2026-02-13

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "8cc4fb5a7ec2"
down_revision: Union[str, None] = "7bb3ea4a6db1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: compatibility revision only. Table creation is in the next revision.
    pass


def downgrade() -> None:
    # No-op
    pass
