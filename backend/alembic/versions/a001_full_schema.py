"""Full schema migration for PostgreSQL

Revision ID: a001_full_schema
Revises: 46e4ea651319
Create Date: 2026-02-18

Uses Base.metadata.create_all to create all 138 tables on PostgreSQL.
On SQLite, tables are already created by init_db(), so this is a no-op.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a001_full_schema'
down_revision = '5b8b15b6a5bd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != 'postgresql':
        return

    # Import all models to populate Base.metadata
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from app.core.database import Base
    import app.models  # noqa: F401 - registers all models with metadata

    Base.metadata.create_all(bind, checkfirst=True)


def downgrade() -> None:
    pass
