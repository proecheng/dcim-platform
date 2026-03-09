"""fix: change JSONB to JSON for SQLite compatibility

Revision ID: cb105f51fc2b
Revises: ad615c658978
Create Date: 2026-03-09 11:44:29.601297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb105f51fc2b'
down_revision: Union[str, None] = 'ad615c658978'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    SQLite 不支持直接修改列类型，但 JSONB 和 JSON 在 SQLite 中都映射为 TEXT，
    因此无需实际修改数据库结构，只需更新 ORM 模型定义即可。

    PostgreSQL 用户需要手动执行：
    ALTER TABLE ab_test_configs ALTER COLUMN strategy_params TYPE JSON USING strategy_params::json;
    ALTER TABLE ab_test_archives ALTER COLUMN version_a_stats TYPE JSON USING version_a_stats::json;
    ALTER TABLE ab_test_archives ALTER COLUMN version_b_stats TYPE JSON USING version_b_stats::json;
    ALTER TABLE ab_test_archives ALTER COLUMN statistical_test_result TYPE JSON USING statistical_test_result::json;
    """
    pass


def downgrade() -> None:
    """
    降级操作：JSON → JSONB（仅 PostgreSQL 需要）

    PostgreSQL 用户需要手动执行：
    ALTER TABLE ab_test_configs ALTER COLUMN strategy_params TYPE JSONB USING strategy_params::jsonb;
    ALTER TABLE ab_test_archives ALTER COLUMN version_a_stats TYPE JSONB USING version_a_stats::jsonb;
    ALTER TABLE ab_test_archives ALTER COLUMN version_b_stats TYPE JSONB USING version_b_stats::jsonb;
    ALTER TABLE ab_test_archives ALTER COLUMN statistical_test_result TYPE JSONB USING statistical_test_result::jsonb;
    """
    pass
