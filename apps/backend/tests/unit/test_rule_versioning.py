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


def test_rule_removed_from_seed_data_is_deactivated_not_deleted(db: Session, monkeypatch):
    """P0 audit fix: a rule (e.g. LMPC-R6-10A-COO-FILTER) that turns out not
    to be supported by the authoritative source must be removable from
    production selection without erasing its historical row/version data —
    'do not silently remove existing rules' means deactivate, never delete."""
    load_rules(db)
    removed_key = "LMPC-R6-1DA-BEST-BEFORE"

    rule = db.query(Rule).filter(Rule.rule_key == removed_key).one()
    assert rule.active is True
    version_count_before = db.query(RuleVersion).filter(RuleVersion.rule_id == rule.id).count()

    patched_seeds = [seed for seed in SEED_RULES if seed["rule_key"] != removed_key]
    monkeypatch.setattr("app.rules.loader.SEED_RULES", patched_seeds)

    summary = load_rules(db)
    assert summary[removed_key] == "deactivated"

    db.expire_all()
    rule = db.query(Rule).filter(Rule.rule_key == removed_key).one()
    assert rule.active is False
    # History is fully preserved -- same row, same versions, nothing deleted.
    assert db.query(RuleVersion).filter(RuleVersion.rule_id == rule.id).count() == version_count_before


def test_deactivated_rule_is_reactivated_if_seed_data_reappears(db: Session, monkeypatch):
    load_rules(db)
    rule_key = "LMPC-R6-1DA-BEST-BEFORE"

    patched_seeds = [seed for seed in SEED_RULES if seed["rule_key"] != rule_key]
    monkeypatch.setattr("app.rules.loader.SEED_RULES", patched_seeds)
    load_rules(db)

    db.expire_all()
    rule = db.query(Rule).filter(Rule.rule_key == rule_key).one()
    assert rule.active is False
    original_version_id = (
        db.query(RuleVersion).filter(RuleVersion.rule_id == rule.id, RuleVersion.is_current.is_(True)).one().id
    )

    monkeypatch.setattr("app.rules.loader.SEED_RULES", SEED_RULES)
    summary = load_rules(db)
    assert summary[rule_key] == "reactivated"

    db.expire_all()
    rule = db.query(Rule).filter(Rule.rule_key == rule_key).one()
    assert rule.active is True
    # Reactivating an unchanged rule must not fabricate a new version.
    current_version = db.query(RuleVersion).filter(
        RuleVersion.rule_id == rule.id, RuleVersion.is_current.is_(True)
    ).one()
    assert current_version.id == original_version_id


def test_lmpc_r6_10a_coo_filter_rule_key_is_not_seeded(db: Session):
    """The purported 'Rule 6(10A)' country-of-origin filter requirement was
    never supported by the authoritative specification and was removed
    (2026-08-28 correction). It must not be present in the active seed set,
    and if a stale row exists in an older database it must load as inactive
    rather than being silently deleted."""
    seed_keys = {seed["rule_key"] for seed in SEED_RULES}
    assert "LMPC-R6-10A-COO-FILTER" not in seed_keys

    # Simulate an older database that still has the stale rule active.
    stale = Rule(rule_key="LMPC-R6-10A-COO-FILTER", active=True)
    db.add(stale)
    db.commit()

    load_rules(db)
    db.expire_all()
    stale = db.query(Rule).filter(Rule.rule_key == "LMPC-R6-10A-COO-FILTER").one()
    assert stale.active is False
