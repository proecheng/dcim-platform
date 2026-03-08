"""merge heads

Revision ID: c7ffe6454eb5
Revises: 20260308_1000, 20260308_1600
Create Date: 2026-03-08 16:27:57.993864

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7ffe6454eb5'
down_revision: Union[str, None] = ('20260308_1000', '20260308_1600')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
