"""create probability_adjustment_logs table

Revision ID: 20260308_0100
Revises: c7ffe6454eb5
Create Date: 2026-03-08 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260308_0100'
down_revision = 'c7ffe6454eb5'
branch_labels = None
depends_on = None


def upgrade():
    # Create probability_adjustment_logs table
    op.create_table(
        'probability_adjustment_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tree_id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.Column('node_name', sa.String(length=200), nullable=False),
        sa.Column('node_type', sa.String(length=20), nullable=False),
        sa.Column('current_probability', sa.Float(), nullable=False),
        sa.Column('proposed_probability', sa.Float(), nullable=False),
        sa.Column('adjustment_percent', sa.Float(), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=False),
        sa.Column('accurate_count', sa.Integer(), nullable=False),
        sa.Column('inaccurate_count', sa.Integer(), nullable=False),
        sa.Column('accuracy_rate', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_adjustment_logs_tree', 'probability_adjustment_logs', ['tree_id'])
    op.create_index('idx_adjustment_logs_node', 'probability_adjustment_logs', ['node_id'])
    op.create_index('idx_adjustment_logs_status', 'probability_adjustment_logs', ['status'])
    op.create_index('idx_adjustment_logs_created', 'probability_adjustment_logs', ['created_at'])
    op.create_index('idx_adjustment_logs_approved_by', 'probability_adjustment_logs', ['approved_by'])

    # Create foreign key constraints (PostgreSQL only, SQLite will skip)
    # Note: Using batch mode for SQLite compatibility
    with op.batch_alter_table('probability_adjustment_logs', schema=None) as batch_op:
        try:
            batch_op.create_foreign_key(
                'fk_adjustment_logs_tree',
                'fault_trees',
                ['tree_id'],
                ['id'],
                ondelete='CASCADE'
            )
            batch_op.create_foreign_key(
                'fk_adjustment_logs_node',
                'fault_tree_nodes',
                ['node_id'],
                ['id'],
                ondelete='CASCADE'
            )
            batch_op.create_foreign_key(
                'fk_adjustment_logs_approved_by',
                'users',
                ['approved_by'],
                ['id'],
                ondelete='SET NULL'
            )
        except Exception:
            # SQLite doesn't support ON DELETE CASCADE in ALTER TABLE
            pass

    # Create trigger for auto-updating updated_at and version (PostgreSQL only)
    # SQLite will skip this
    try:
        op.execute("""
            CREATE OR REPLACE FUNCTION update_adjustment_logs_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                NEW.version = OLD.version + 1;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)

        op.execute("""
            CREATE TRIGGER trigger_update_adjustment_logs_updated_at
            BEFORE UPDATE ON probability_adjustment_logs
            FOR EACH ROW
            EXECUTE FUNCTION update_adjustment_logs_updated_at();
        """)
    except Exception:
        # SQLite doesn't support this syntax
        pass


def downgrade():
    # Drop trigger and function (PostgreSQL only)
    try:
        op.execute("DROP TRIGGER IF EXISTS trigger_update_adjustment_logs_updated_at ON probability_adjustment_logs;")
        op.execute("DROP FUNCTION IF EXISTS update_adjustment_logs_updated_at();")
    except Exception:
        pass

    # Drop table (cascades indexes and constraints)
    op.drop_table('probability_adjustment_logs')
