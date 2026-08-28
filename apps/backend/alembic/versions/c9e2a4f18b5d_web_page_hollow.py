"""add web_pages.hollow (hollow-scrape evidence-quality fix)

Revision ID: c9e2a4f18b5d
Revises: b4f2a9c1d7e3
Create Date: 2026-08-28 09:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9e2a4f18b5d'
down_revision: Union[str, None] = 'b4f2a9c1d7e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A fetch that HTTP-succeeded but yielded no real product data (a
    # marketplace serving its generic homepage instead of the listing) was
    # previously indistinguishable, for evidence-quality scoring purposes,
    # from a genuinely successful scrape — defaults False so every existing
    # WebPage row is treated exactly as it already was.
    op.add_column(
        'web_pages',
        sa.Column('hollow', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('web_pages', 'hollow')
