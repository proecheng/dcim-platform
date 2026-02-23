"""merge_heads

Revision ID: 5d8aefd3d9df
Revises: 202602210001, a002_timescaledb_hypertable
Create Date: 2026-02-23 11:40:18.748154

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "5d8aefd3d9df"
down_revision: Union[str, None] = ("202602210001", "a002_timescaledb_hypertable")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
