"""Create time_window_adjustment_logs and audit_logs tables

Revision ID: 20260308_0200
Revises: 20260308_1000
Create Date: 2026-03-08 02:00:00.000000

Story 26.4: 时间窗口自适应
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260308_0200'
down_revision: Union[str, None] = '77468b53feb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 audit_logs 表（通用审计日志表）
    # 注意：使用 IF NOT EXISTS 避免重复创建
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(50) NOT NULL,
            resource_id INTEGER,
            details TEXT,
            ip_address VARCHAR(50),
            user_agent VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    # 创建索引
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)")

    # 创建 time_window_adjustment_logs 表
    op.create_table(
        'time_window_adjustment_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_type', sa.String(length=100), nullable=False),
        sa.Column('current_window_minutes', sa.Integer(), nullable=False),
        sa.Column('proposed_window_minutes', sa.Integer(), nullable=False),
        sa.Column('adjustment_percent', sa.Float(), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=False),
        sa.Column('p50_duration_seconds', sa.Float(), nullable=False),
        sa.Column('p90_duration_seconds', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index('idx_adjustment_logs_device_type', 'time_window_adjustment_logs', ['device_type'])
    op.create_index('idx_adjustment_logs_status', 'time_window_adjustment_logs', ['status'])
    op.create_index('idx_adjustment_logs_created', 'time_window_adjustment_logs', ['created_at'])
    op.create_index('idx_adjustment_logs_approved_by', 'time_window_adjustment_logs', ['approved_by'])

    # 创建触发器（自动更新 updated_at 和 version）
    # SQLite 触发器语法
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS trigger_update_adjustment_logs_updated_at
        AFTER UPDATE ON time_window_adjustment_logs
        FOR EACH ROW
        BEGIN
            UPDATE time_window_adjustment_logs
            SET updated_at = CURRENT_TIMESTAMP,
                version = OLD.version + 1
            WHERE id = NEW.id;
        END;
    """)


def downgrade() -> None:
    # 删除触发器
    op.execute("DROP TRIGGER IF EXISTS trigger_update_adjustment_logs_updated_at")

    # 删除索引
    op.drop_index('idx_adjustment_logs_approved_by', table_name='time_window_adjustment_logs')
    op.drop_index('idx_adjustment_logs_created', table_name='time_window_adjustment_logs')
    op.drop_index('idx_adjustment_logs_status', table_name='time_window_adjustment_logs')
    op.drop_index('idx_adjustment_logs_device_type', table_name='time_window_adjustment_logs')

    # 删除表
    op.drop_table('time_window_adjustment_logs')

    # 删除 audit_logs 表的索引和表
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_created_at")
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_resource")
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_action")
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_user_id")
    op.execute("DROP TABLE IF EXISTS audit_logs")
