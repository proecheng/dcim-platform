"""merge heads

Revision ID: e5fbbe704523
Revises: 20260308_0100, 20260308_0200
Create Date: 2026-03-09 11:05:33.078950

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5fbbe704523'
down_revision: Union[str, None] = ('20260308_0100', '20260308_0200')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
