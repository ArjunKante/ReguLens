"""nullable source_url (manual/photo-only inspections)

Revision ID: e77761489d8f
Revises: 2caf02dcb91f
Create Date: 2026-08-26 19:05:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e77761489d8f'
down_revision: Union[str, None] = '2caf02dcb91f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Lets an inspection be started from uploaded/captured photos alone, with
    # no product listing URL at all — not just as a fallback after a failed
    # automatic fetch (that path already worked; this is the new "manual
    # scan" entry point on the New Inspection page).
    op.alter_column('inspections', 'source_url', existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column('inspections', 'source_url', existing_type=sa.Text(), nullable=False)
