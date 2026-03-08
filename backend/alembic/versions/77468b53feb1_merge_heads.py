"""merge heads

Revision ID: 77468b53feb1
Revises: 20260308_0000, c7ffe6454eb5
Create Date: 2026-03-08 18:28:53.678972

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77468b53feb1'
down_revision: Union[str, None] = ('20260308_0000', 'c7ffe6454eb5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
