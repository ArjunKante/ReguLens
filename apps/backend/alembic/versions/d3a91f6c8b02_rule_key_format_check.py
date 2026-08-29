"""add rules.rule_key format CHECK constraint (rule_key XSS-safety fix)

Revision ID: d3a91f6c8b02
Revises: c9e2a4f18b5d
Create Date: 2026-08-29 09:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = 'd3a91f6c8b02'
down_revision: Union[str, None] = 'c9e2a4f18b5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Report rendering (app/reports/context.py::break_identifier) renders
# rule_key into generated PDF/HTML reports with Jinja2 autoescaping bypassed
# (`|safe`), on the assumption that a rule_key is always an uppercase
# letters/digits/hyphens identifier (e.g. "LMPC-R6-1E-MRP") and therefore
# can never carry HTML/script content. That assumption was previously
# enforced nowhere -- neither at the API schema layer nor here. This
# migration adds the database-level half of the fix (see
# app/schemas/rules.py::RULE_KEY_PATTERN for the API-layer half). Every
# rule_key currently seeded by app/rules/seed_rules.py already matches this
# pattern, so this is a no-op against existing data.
_CHECK_SQL = r"rule_key ~ '^[A-Z0-9]+(-[A-Z0-9]+)*$'"


def upgrade() -> None:
    op.create_check_constraint("ck_rules_rule_key_format", "rules", _CHECK_SQL)


def downgrade() -> None:
    op.drop_constraint("ck_rules_rule_key_format", "rules", type_="check")
