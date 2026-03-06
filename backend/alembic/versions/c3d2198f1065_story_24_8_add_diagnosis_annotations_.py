"""Story 24.8: Add diagnosis_annotations table

Revision ID: c3d2198f1065
Revises: b2c3d4e5f6a7
Create Date: 2026-03-06 19:01:08.155089

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d2198f1065'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create diagnosis_annotations table
    op.create_table(
        'diagnosis_annotations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False, comment='诊断会话ID'),
        sa.Column('annotator_id', sa.Integer(), nullable=True, comment='标注者ID'),
        sa.Column('annotation', sa.String(length=20), nullable=False, comment='标注结果: accurate/inaccurate/unknown'),
        sa.Column('actual_root_cause', sa.Text(), nullable=True, comment='实际根因(标注为inaccurate时必填)'),
        sa.Column('notes', sa.Text(), nullable=True, comment='备注'),
        sa.Column('annotated_at', sa.DateTime(), nullable=False, comment='标注时间'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['annotator_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['diagnosis_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("annotation IN ('accurate', 'inaccurate', 'unknown')", name='check_annotation_values'),
        sa.CheckConstraint("annotation != 'inaccurate' OR actual_root_cause IS NOT NULL", name='check_actual_root_cause'),
        sa.CheckConstraint("actual_root_cause IS NULL OR length(actual_root_cause) <= 1000", name='check_actual_root_cause_length'),
        sa.CheckConstraint("notes IS NULL OR length(notes) <= 2000", name='check_notes_length')
    )

    # Create indexes
    op.create_index('ix_diagnosis_annotations_session_id', 'diagnosis_annotations', ['session_id'])
    op.create_index('ix_diagnosis_annotations_annotator_id', 'diagnosis_annotations', ['annotator_id'])
    op.create_index('ix_diagnosis_annotations_session_annotation', 'diagnosis_annotations', ['session_id', 'annotation'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_diagnosis_annotations_session_annotation', table_name='diagnosis_annotations')
    op.drop_index('ix_diagnosis_annotations_annotator_id', table_name='diagnosis_annotations')
    op.drop_index('ix_diagnosis_annotations_session_id', table_name='diagnosis_annotations')

    # Drop table
    op.drop_table('diagnosis_annotations')
