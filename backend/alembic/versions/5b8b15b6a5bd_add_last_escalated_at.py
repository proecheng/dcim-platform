"""add_last_escalated_at

Revision ID: 5b8b15b6a5bd
Revises: 78a19e60c4a2
Create Date: 2026-02-16 12:49:48.020746

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5b8b15b6a5bd"
down_revision: Union[str, None] = "78a19e60c4a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("alarms", sa.Column("last_escalated_at", sa.DateTime(), nullable=True, comment="最后升级时间"))


def downgrade() -> None:
    op.drop_column("alarms", "last_escalated_at")
