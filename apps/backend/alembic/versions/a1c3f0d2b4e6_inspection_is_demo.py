"""add inspections.is_demo (Demo Inspection mode)

Revision ID: a1c3f0d2b4e6
Revises: e77761489d8f
Create Date: 2026-08-26 23:05:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c3f0d2b4e6'
down_revision: Union[str, None] = 'e77761489d8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Demo Hardening: a controlled, reproducible, network-independent
    # inspection path for live demos, clearly distinguished from a real
    # inspection everywhere it's displayed (never presented as a real
    # finding). Defaults False so every existing/real inspection is
    # unaffected.
    op.add_column(
        'inspections',
        sa.Column('is_demo', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('inspections', 'is_demo')
