from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.audit.service import log_action
from app.auth.dependencies import require_admin, require_any_authenticated
from app.core.database import get_db
from app.models.rules import Rule
from app.models.user import User
from app.rules.loader import _build_version, _content_hash  # reuse versioning logic
from app.schemas.rules import RuleCreate, RuleOut, RuleVersionCreate, RuleVersionOut

router = APIRouter(prefix="/rules", tags=["rules"])


def _to_rule_out(rule: Rule) -> RuleOut:
    current = next((v for v in rule.versions if v.is_current), None)
    return RuleOut(
        id=rule.id,
        rule_key=rule.rule_key,
        active=rule.active,
        current_version=RuleVersionOut.model_validate(current) if current else None,
    )


@router.get("", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db), _user: User = Depends(require_any_authenticated)) -> list[RuleOut]:
    rules = db.query(Rule).options(selectinload(Rule.versions)).order_by(Rule.rule_key).all()
    return [_to_rule_out(r) for r in rules]


@router.get("/{rule_key}/versions", response_model=list[RuleVersionOut])
def get_rule_versions(
    rule_key: str, db: Session = Depends(get_db), _user: User = Depends(require_any_authenticated)
) -> list[RuleVersionOut]:
    rule = db.query(Rule).filter(Rule.rule_key == rule_key).one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found.")
    versions = sorted(rule.versions, key=lambda v: v.version_number)
    return [RuleVersionOut.model_validate(v) for v in versions]


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: RuleCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> RuleOut:
    existing = db.query(Rule).filter(Rule.rule_key == payload.rule_key).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="A rule with this rule_key already exists; use PUT to update it.")

    rule = Rule(rule_key=payload.rule_key, active=True)
    db.add(rule)
    db.flush()

    seed = payload.model_dump(exclude={"rule_key"})
    seed["effective_from"] = payload.effective_from.isoformat() if payload.effective_from else None
    seed["effective_until"] = payload.effective_until.isoformat() if payload.effective_until else None
    seed["validation_type"] = payload.validation_type.value
    seed["severity"] = payload.severity.value

    version = _build_version(rule.id, 1, seed)
    db.add(version)
    db.commit()
    db.refresh(rule)

    log_action(db, actor_id=admin.id, action="RULE_CREATED", entity_type="rule", entity_id=str(rule.id), extra={"rule_key": rule.rule_key})
    return _to_rule_out(rule)


@router.put("/{rule_key}", response_model=RuleOut)
def update_rule(
    rule_key: str, payload: RuleVersionCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> RuleOut:
    """Creates a NEW RuleVersion for this rule (Section 12: rule versioning
    — historical inspections keep referencing the OLD version; only future
    inspections see the update)."""
    rule = db.query(Rule).options(selectinload(Rule.versions)).filter(Rule.rule_key == rule_key).one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found.")

    current = next((v for v in rule.versions if v.is_current), None)
    seed = payload.model_dump()
    seed["effective_from"] = payload.effective_from.isoformat() if payload.effective_from else None
    seed["effective_until"] = payload.effective_until.isoformat() if payload.effective_until else None
    seed["validation_type"] = payload.validation_type.value
    seed["severity"] = payload.severity.value

    if current is not None:
        current_seed = {
            "rule_reference": current.rule_reference, "title": current.title, "description": current.description,
            "requirement": current.requirement, "applicability": current.applicability, "exceptions": current.exceptions,
            "validation_type": current.validation_type, "severity": current.severity,
            "validator_config": current.validator_config, "applicable_categories": current.applicable_categories,
            "excluded_categories": current.excluded_categories, "gating_only": current.gating_only,
            "source_document": current.source_document, "source_locator": current.source_locator,
            "effective_from": current.effective_from.isoformat() if current.effective_from else None,
            "effective_until": current.effective_until.isoformat() if current.effective_until else None,
            "notes": current.notes,
        }
        if _content_hash(current_seed) == _content_hash(seed):
            return _to_rule_out(rule)
        current.is_current = False

    next_version_number = (current.version_number + 1) if current else 1
    version = _build_version(rule.id, next_version_number, seed)
    db.add(version)
    db.commit()
    db.refresh(rule)

    log_action(
        db, actor_id=admin.id, action="RULE_UPDATED", entity_type="rule", entity_id=str(rule.id),
        extra={"rule_key": rule.rule_key, "new_version": next_version_number},
    )
    return _to_rule_out(rule)
