"""add inspection_batches table + inspections.batch_id (bulk/batch scan)

Revision ID: b4f2a9c1d7e3
Revises: a1c3f0d2b4e6
Create Date: 2026-08-27 10:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4f2a9c1d7e3'
down_revision: Union[str, None] = 'a1c3f0d2b4e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Bulk/batch scan + triage queue: a batch is a label tying together a
    # group of ordinary Inspection rows (see app/models/batch.py) — no
    # existing table's shape changes beyond the new nullable batch_id FK.
    op.create_table(
        'inspection_batches',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('created_by_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('total_count', sa.Integer(), nullable=False),
        sa.Column('rejected_urls', sa.JSON(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_inspection_batches_id'), 'inspection_batches', ['id'])
    op.create_index(op.f('ix_inspection_batches_status'), 'inspection_batches', ['status'])

    op.add_column('inspections', sa.Column('batch_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_inspections_batch_id'), 'inspections', ['batch_id'])
    op.create_foreign_key(
        'fk_inspections_batch_id_inspection_batches',
        'inspections', 'inspection_batches', ['batch_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_inspections_batch_id_inspection_batches', 'inspections', type_='foreignkey')
    op.drop_index(op.f('ix_inspections_batch_id'), table_name='inspections')
    op.drop_column('inspections', 'batch_id')

    op.drop_index(op.f('ix_inspection_batches_status'), table_name='inspection_batches')
    op.drop_index(op.f('ix_inspection_batches_id'), table_name='inspection_batches')
    op.drop_table('inspection_batches')
