"""add_escalation_chain_column

Revision ID: a7634211706c
Revises: 5d8aefd3d9df
Create Date: 2026-02-23 11:40:37.249523

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a7634211706c"
down_revision: Union[str, None] = "5d8aefd3d9df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "alarm_escalations",
        sa.Column(
            "escalation_chain",
            sa.Text(),
            nullable=True,
            comment="升级链JSON(节点数组)",
        ),
    )


def downgrade() -> None:
    op.drop_column("alarm_escalations", "escalation_chain")
