"""Aggregation queries backing the dashboard (Section 18)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.compliance import ComplianceCheck, Violation
from app.models.inspection import Inspection
from app.models.product import Product, ProductCategory
from app.models.rules import Rule, RuleVersion
from app.schemas.dashboard import CountByKey, DashboardStatistics, TrendPoint


def get_dashboard_statistics(db: Session) -> DashboardStatistics:
    total = db.execute(select(func.count(Inspection.id))).scalar_one()

    def _count_status(value: str) -> int:
        return db.execute(
            select(func.count(Inspection.id)).where(Inspection.overall_status == value)
        ).scalar_one()

    passed = _count_status("PASS")
    potential = _count_status("POTENTIAL_NON_COMPLIANCE")
    needs_review = _count_status("NEEDS_MANUAL_REVIEW")
    unable = _count_status("UNABLE_TO_VERIFY")
    not_applicable_only = _count_status("NOT_APPLICABLE")

    by_platform_rows = db.execute(
        select(Inspection.platform, func.count(Inspection.id))
        .where(Inspection.platform.is_not(None))
        .group_by(Inspection.platform)
    ).all()
    by_platform = [CountByKey(key=k or "unknown", count=c) for k, c in by_platform_rows]

    by_category_rows = db.execute(
        select(ProductCategory.name, func.count(Product.id))
        .join(Product, Product.category_id == ProductCategory.id)
        .group_by(ProductCategory.name)
    ).all()
    by_category = [CountByKey(key=k, count=c) for k, c in by_category_rows]

    violations_by_rule_rows = db.execute(
        select(Rule.rule_key, func.count(Violation.id))
        .join(ComplianceCheck, ComplianceCheck.id == Violation.compliance_check_id)
        .join(RuleVersion, RuleVersion.id == ComplianceCheck.rule_version_id)
        .join(Rule, Rule.id == RuleVersion.rule_id)
        .group_by(Rule.rule_key)
        .order_by(func.count(Violation.id).desc())
        .limit(10)
    ).all()
    violations_by_rule = [CountByKey(key=k, count=c) for k, c in violations_by_rule_rows]

    common_issues_rows = db.execute(
        select(RuleVersion.title, func.count(Violation.id))
        .join(ComplianceCheck, ComplianceCheck.id == Violation.compliance_check_id)
        .join(RuleVersion, RuleVersion.id == ComplianceCheck.rule_version_id)
        .group_by(RuleVersion.title)
        .order_by(func.count(Violation.id).desc())
        .limit(5)
    ).all()
    common_issues = [CountByKey(key=k, count=c) for k, c in common_issues_rows]

    review_backlog = db.execute(
        select(func.count(func.distinct(ComplianceCheck.id)))
        .outerjoin(ComplianceCheck.review_decisions)
        .where(ComplianceCheck.status == "POTENTIAL_NON_COMPLIANCE")
        .where(~ComplianceCheck.review_decisions.any())
    ).scalar_one()

    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
    trend_rows = db.execute(
        select(func.date(Inspection.created_at), func.count(Inspection.id))
        .where(Inspection.created_at >= since)
        .group_by(func.date(Inspection.created_at))
        .order_by(func.date(Inspection.created_at))
    ).all()
    trend = [TrendPoint(date=d, count=c) for d, c in trend_rows]

    return DashboardStatistics(
        total_online_inspections=total,
        passed=passed,
        potential_violations=potential,
        needs_review=needs_review,
        unable_to_verify=unable,
        not_applicable_only=not_applicable_only,
        by_platform=by_platform,
        by_category=by_category,
        violations_by_rule=violations_by_rule,
        common_issues=common_issues,
        review_backlog=review_backlog,
        trend_last_30_days=trend,
    )
