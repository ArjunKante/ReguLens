"""Rule versioning tests (Section 12): editing a rule must never change what
a historical inspection's ComplianceCheck rows point to."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.rules import Rule, RuleVersion
from app.rules.loader import load_rules
from app.rules.seed_rules import SEED_RULES


def test_loading_twice_is_idempotent(db: Session):
    summary1 = load_rules(db)
    assert all(v == "created" for v in summary1.values())
    summary2 = load_rules(db)
    assert all(v == "unchanged" for v in summary2.values())


def test_changing_a_rule_creates_a_new_version_and_keeps_the_old_one(db: Session, monkeypatch):
    load_rules(db)
    rule_key = "LMPC-R6-1E-MRP"

    rule = db.query(Rule).filter(Rule.rule_key == rule_key).one()
    old_version = db.query(RuleVersion).filter(RuleVersion.rule_id == rule.id, RuleVersion.is_current.is_(True)).one()
    old_version_id = old_version.id
    old_requirement_text = old_version.requirement

    # Simulate an admin edit: change the seed data for this one rule and reload.
    patched_seeds = []
    for seed in SEED_RULES:
        if seed["rule_key"] == rule_key:
            seed = dict(seed)
            seed["requirement"] = seed["requirement"] + " (Amended for test.)"
        patched_seeds.append(seed)
    monkeypatch.setattr("app.rules.loader.SEED_RULES", patched_seeds)

    summary = load_rules(db)
    assert summary[rule_key] == "new_version"

    db.expire_all()
    new_current = db.query(RuleVersion).filter(RuleVersion.rule_id == rule.id, RuleVersion.is_current.is_(True)).one()
    assert new_current.id != old_version_id
    assert new_current.version_number == old_version.version_number + 1
    assert "(Amended for test.)" in new_current.requirement

    # The OLD version row must still exist, unmodified, for historical traceability.
    preserved_old = db.get(RuleVersion, old_version_id)
    assert preserved_old is not None
    assert preserved_old.is_current is False
    assert preserved_old.requirement == old_requirement_text
