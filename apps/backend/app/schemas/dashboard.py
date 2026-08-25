from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class CountByKey(BaseModel):
    key: str
    count: int


class TrendPoint(BaseModel):
    date: dt.date
    count: int


class DashboardStatistics(BaseModel):
    total_online_inspections: int
    passed: int
    potential_violations: int
    needs_review: int
    unable_to_verify: int
    not_applicable_only: int

    by_platform: list[CountByKey]
    by_category: list[CountByKey]
    violations_by_rule: list[CountByKey]
    common_issues: list[CountByKey]
    review_backlog: int
    trend_last_30_days: list[TrendPoint]
