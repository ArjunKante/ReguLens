"""Loads SEED_RULES into the `rules` / `rule_versions` tables.

Idempotent and versioning-aware: if a rule's content is unchanged since the
last load, nothing happens. If it changed, a new RuleVersion is appended
(the old version is kept, flagged is_current=False) rather than mutated in
place — this is what makes historical inspections reproducible (Section 12).

Run directly with: python -m app.rules.loader
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.rules import Rule, RuleVersion
from app.rules.seed_rules import SEED_RULES, SeedRule

CONTENT_FIELDS = (
    "rule_reference",
    "title",
    "description",
    "requirement",
    "applicability",
    "exceptions",
    "validation_type",
    "severity",
    "validator_config",
    "applicable_categories",
    "excluded_categories",
    "gating_only",
    "source_document",
    "source_locator",
    "effective_from",
    "effective_until",
    "notes",
)


def _normalize(seed: Mapping[str, Any]) -> dict:
    """Apply the same defaulting `_build_version` applies, so a freshly
    authored seed dict and one round-tripped through the DB hash identically."""
    return {
        "rule_reference": seed.get("rule_reference"),
        "title": seed.get("title"),
        "description": seed.get("description"),
        "requirement": seed.get("requirement"),
        "applicability": seed.get("applicability"),
        "exceptions": seed.get("exceptions"),
        "validation_type": seed.get("validation_type"),
        "severity": seed.get("severity"),
        "validator_config": dict(seed.get("validator_config") or {}),
        "applicable_categories": seed.get("applicable_categories") or [],
        "excluded_categories": seed.get("excluded_categories") or [],
        "gating_only": bool(seed.get("gating_only", False)),
        "source_document": seed.get("source_document"),
        "source_locator": seed.get("source_locator"),
        "effective_from": seed.get("effective_from"),
        "effective_until": seed.get("effective_until"),
        "notes": seed.get("notes"),
    }


def _content_hash(seed: Mapping[str, Any]) -> str:
    payload = {k: _normalize(seed)[k] for k in CONTENT_FIELDS}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def load_rules(db: Session) -> dict[str, str]:
    """Returns a summary dict: rule_key -> 'created' | 'new_version' | 'unchanged'
    | 'reactivated' | 'deactivated'.

    A rule_key present in the DB but no longer present in SEED_RULES is
    deactivated (`Rule.active = False`), never deleted — its `RuleVersion`
    history is left intact so past inspections stay reproducible (Section
    12) and the removal itself stays auditable. A deactivated rule is
    excluded from the compliance engine's active-rule query
    (`app/compliance/engine.py::_active_rule_versions`, which filters on
    `Rule.active.is_(True)`), so it stops producing new ComplianceCheck rows
    without erasing what it already produced historically. If a rule_key
    that was previously deactivated this way reappears in SEED_RULES, it is
    reactivated (`Rule.active = True`) rather than treated as brand new,
    preserving its original identity/version history.
    """
    summary: dict[str, str] = {}
    seed_keys = {seed["rule_key"] for seed in SEED_RULES}

    for seed in SEED_RULES:
        rule = db.query(Rule).filter(Rule.rule_key == seed["rule_key"]).one_or_none()
        new_hash = _content_hash(seed)

        if rule is None:
            rule = Rule(rule_key=seed["rule_key"], active=True)
            db.add(rule)
            db.flush()
            version = _build_version(rule.id, 1, seed)
            db.add(version)
            summary[seed["rule_key"]] = "created"
            continue

        was_inactive = not rule.active
        if was_inactive:
            rule.active = True

        current_version = (
            db.query(RuleVersion)
            .filter(RuleVersion.rule_id == rule.id, RuleVersion.is_current.is_(True))
            .one_or_none()
        )
        current_hash = (
            _content_hash(_version_to_seed_dict(current_version)) if current_version else None
        )

        if current_version is not None and current_hash == new_hash:
            summary[seed["rule_key"]] = "reactivated" if was_inactive else "unchanged"
            continue

        next_version_number = (current_version.version_number + 1) if current_version else 1
        if current_version is not None:
            current_version.is_current = False
        version = _build_version(rule.id, next_version_number, seed)
        db.add(version)
        summary[seed["rule_key"]] = "reactivated" if was_inactive else "new_version"

    # Deactivate (never delete) any rule whose rule_key has disappeared from
    # SEED_RULES — e.g. a rule later found not to be supported by the
    # authoritative source. History stays intact; the engine simply stops
    # selecting it (see docstring above).
    stale_rules = db.query(Rule).filter(Rule.active.is_(True), ~Rule.rule_key.in_(seed_keys)).all()
    for rule in stale_rules:
        rule.active = False
        summary[rule.rule_key] = "deactivated"

    db.commit()
    return summary


def _version_to_seed_dict(version: RuleVersion) -> SeedRule:
    return {  # type: ignore[return-value]
        "rule_reference": version.rule_reference,
        "title": version.title,
        "description": version.description,
        "requirement": version.requirement,
        "applicability": version.applicability,
        "exceptions": version.exceptions,
        "validation_type": version.validation_type,
        "severity": version.severity,
        "validator_config": version.validator_config,
        "applicable_categories": version.applicable_categories,
        "excluded_categories": version.excluded_categories,
        "gating_only": version.gating_only,
        "source_document": version.source_document,
        "source_locator": version.source_locator,
        "effective_from": version.effective_from.isoformat() if version.effective_from else None,
        "effective_until": version.effective_until.isoformat() if version.effective_until else None,
        "notes": version.notes,
    }


def _build_version(rule_id, version_number: int, seed: Mapping[str, Any]) -> RuleVersion:  # type: ignore[no-untyped-def]
    effective_from = seed.get("effective_from")
    effective_until = seed.get("effective_until")
    return RuleVersion(
        rule_id=rule_id,
        version_number=version_number,
        rule_reference=seed["rule_reference"],
        title=seed["title"],
        description=seed["description"],
        requirement=seed["requirement"],
        applicability=seed["applicability"],
        exceptions=seed.get("exceptions"),
        validation_type=seed["validation_type"],
        severity=seed["severity"],
        validator_config=dict(seed.get("validator_config") or {}),
        applicable_categories=seed.get("applicable_categories") or [],
        excluded_categories=seed.get("excluded_categories") or [],
        gating_only=bool(seed.get("gating_only", False)),
        source_document=seed["source_document"],
        source_locator=seed["source_locator"],
        effective_from=dt.date.fromisoformat(effective_from) if effective_from else None,
        effective_until=dt.date.fromisoformat(effective_until) if effective_until else None,
        notes=seed.get("notes"),
        is_current=True,
    )


def run() -> None:
    db = SessionLocal()
    try:
        summary = load_rules(db)
        for key, outcome in summary.items():
            print(f"{key}: {outcome}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
