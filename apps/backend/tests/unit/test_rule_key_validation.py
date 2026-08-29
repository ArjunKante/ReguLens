"""REPORT BUG 3 regression: rule_key format enforcement.

app/reports/context.py::break_identifier renders a RuleVersion's rule_key
into generated PDF/HTML reports with Jinja2 autoescaping bypassed (`|safe`),
on the assumption that a rule_key is always an uppercase letters/digits/
hyphens identifier and therefore can never carry HTML/script content. This
used to be an unenforced comment. These tests confirm the format is now
actually enforced at both the API schema layer (Pydantic) and the database
layer (a CHECK constraint), and that no currently-seeded rule_key is broken
by the new pattern.
"""
from __future__ import annotations

import re
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.rules import Rule
from app.rules.seed_rules import SEED_RULES
from app.schemas.rules import RULE_KEY_PATTERN, RuleCreate

_VALID_PAYLOAD_FIELDS = dict(
    rule_reference="Rule X",
    title="Test rule",
    description="Test.",
    requirement="Test.",
    applicability="All.",
    validation_type="PRESENCE_CHECK",
    severity="MAJOR",
    source_document="Test Source",
    source_locator="Rule X",
)


@pytest.mark.parametrize(
    "rule_key",
    ["LMPC-R6-1E-MRP", "LMSCAN-CONSISTENCY-MRP", "A", "A1-B2", "LMPC-R6-10A-COO-FILTER"],
)
def test_valid_rule_keys_are_accepted(rule_key: str):
    payload = RuleCreate(rule_key=rule_key, **_VALID_PAYLOAD_FIELDS)
    assert payload.rule_key == rule_key


@pytest.mark.parametrize(
    "rule_key",
    [
        "<script>alert(1)</script>",
        "LMPC-R6-1E-MRP<img src=x onerror=alert(1)>",
        "lowercase-key",
        "HAS SPACE",
        "HAS_UNDERSCORE",
        "",
        "TRAILING-HYPHEN-",
        "-LEADING-HYPHEN",
    ],
)
def test_html_like_and_malformed_rule_keys_are_rejected(rule_key: str):
    with pytest.raises(ValidationError):
        RuleCreate(rule_key=rule_key, **_VALID_PAYLOAD_FIELDS)


def test_every_seeded_rule_key_matches_the_enforced_pattern():
    """The new pattern must not break any rule_key already in production
    use -- including the deactivated-but-preserved LMPC-R6-10A-COO-FILTER
    row (see docs/legal-rules.md's revision history)."""
    pattern = re.compile(RULE_KEY_PATTERN)
    for seed in SEED_RULES:
        assert pattern.match(seed["rule_key"]), f"{seed['rule_key']!r} no longer matches RULE_KEY_PATTERN"


def test_database_check_constraint_rejects_a_malicious_rule_key(db: Session):
    """Defense in depth: even bypassing the Pydantic schema entirely (e.g. a
    direct ORM insert), the database itself refuses a rule_key that isn't a
    plain uppercase/digit/hyphen identifier."""
    bad_rule = Rule(rule_key="<script>alert(1)</script>", active=True)
    db.add(bad_rule)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_database_check_constraint_accepts_a_normal_rule_key(db: Session):
    good_rule = Rule(rule_key=f"TEST-RULE-{uuid.uuid4().hex[:8].upper()}", active=True)
    db.add(good_rule)
    db.commit()  # must not raise
    db.refresh(good_rule)
    assert good_rule.id is not None
