"""add_pricing_schemes

Revision ID: d27a98f5eea8
Revises: a7634211706c
Create Date: 2026-03-02 12:22:33.075660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd27a98f5eea8'
down_revision: Union[str, None] = 'a7634211706c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 创建 pricing_schemes 表
    op.create_table(
        'pricing_schemes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scheme_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('expire_date', sa.Date(), nullable=True),
        sa.Column('validation_result', sa.JSON(), nullable=True),
        sa.Column('validation_time', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建唯一索引（只允许一个激活方案）
    op.create_index(
        'idx_active_scheme',
        'pricing_schemes',
        ['is_active'],
        unique=True,
        sqlite_where=sa.text('is_active = 1')
    )
    
    # 2. 创建 scheme_pricing_relations 表
    op.create_table(
        'scheme_pricing_relations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scheme_id', sa.Integer(), nullable=False),
        sa.Column('pricing_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['scheme_id'], ['pricing_schemes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pricing_id'], ['electricity_pricing.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scheme_id', 'pricing_id', name='uq_scheme_pricing')
    )
    
    # 3. 创建审计日志表
    op.create_table(
        'pricing_scheme_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scheme_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['scheme_id'], ['pricing_schemes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 4. 数据迁移：将现有已启用时段组合成默认方案
    conn = op.get_bind()
    
    # 查询已启用的时段
    enabled_pricings = conn.execute(
        sa.text("SELECT * FROM electricity_pricing WHERE is_enabled = 1")
    ).fetchall()
    
    if enabled_pricings:
        # 创建默认方案
        conn.execute(
            sa.text(
                "INSERT INTO pricing_schemes "
                "(scheme_name, description, is_active, effective_date) "
                "VALUES (:name, :desc, 1, date('now'))"
            ),
            {
                "name": "默认电价方案",
                "desc": "由现有已启用时段自动生成"
            }
        )
        
        # 获取刚创建的方案ID
        scheme_id = conn.execute(
            sa.text("SELECT id FROM pricing_schemes WHERE scheme_name = '默认电价方案')")
        ).scalar()
        
        # 关联所有已启用时段
        for pricing in enabled_pricings:
            conn.execute(
                sa.text(
                    "INSERT INTO scheme_pricing_relations (scheme_id, pricing_id) "
                    "VALUES (:scheme_id, :pricing_id)"
                ),
                {"scheme_id": scheme_id, "pricing_id": pricing['id']}
            )
        
        print(f"✅ 数据迁移成功：创建默认方案，关联 {len(enabled_pricings)} 个时段")
    else:
        print("⚠️  没有已启用的时段，跳过默认方案创建")


def downgrade() -> None:
    # 回滚：删除表
    op.drop_table('pricing_scheme_audit_logs')
    op.drop_table('scheme_pricing_relations')
    op.drop_index('idx_active_scheme', table_name='pricing_schemes')
    op.drop_table('pricing_schemes')
