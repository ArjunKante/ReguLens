"""Triage ranking for the bulk/batch scan queue.

Sorting a batch's inspections by `triage_sort_key` surfaces the most
severe, most-confidently-flagged listings first, so an officer scanning
hundreds of results doesn't have to open each one to find the ones that
matter. This deliberately reuses the same ComplianceStatus severity
ordering already established in `compliance/engine.py::_STATUS_PRIORITY`
rather than inventing a second, inconsistent ranking.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.inspection import Inspection

# Lower = more urgent. Mirrors compliance/engine.py::_STATUS_PRIORITY, with
# NOT_APPLICABLE folded in alongside PASS — an inspection whose applicable
# rules all passed and one whose rules were all not-applicable are equally
# "nothing to triage here" from an officer's point of view.
_SEVERITY_ORDER = {
    "POTENTIAL_NON_COMPLIANCE": 0,
    "NEEDS_MANUAL_REVIEW": 1,
    "UNABLE_TO_VERIFY": 2,
    "PASS": 3,
    "NOT_APPLICABLE": 3,
}
_UNKNOWN_SEVERITY = 4  # overall_status is None (e.g. still IN_PROGRESS)


@dataclass(frozen=True)
class TriageMetrics:
    violation_count: int
    critical_violation_count: int
    max_violation_confidence: float


def triage_metrics(inspection: Inspection) -> TriageMetrics:
    """Reads only relationships `repositories/batch_repository.py::get_batch`
    already eager-loads (compliance_checks -> violation, rule_version.rule),
    so this never triggers an N+1 query."""
    violations = [c.violation for c in inspection.compliance_checks if c.violation is not None]
    critical = sum(1 for v in violations if v.severity == "CRITICAL")
    max_conf = max(
        (c.confidence for c in inspection.compliance_checks if c.violation is not None), default=0.0
    )
    return TriageMetrics(
        violation_count=len(violations),
        critical_violation_count=critical,
        max_violation_confidence=max_conf,
    )


def triage_sort_key(inspection: Inspection) -> tuple[int, int, int, float]:
    """Ascending sort key: most severe / most violations / most confident
    violations first."""
    m = triage_metrics(inspection)
    severity = _SEVERITY_ORDER.get(inspection.overall_status or "", _UNKNOWN_SEVERITY)
    return (severity, -m.critical_violation_count, -m.violation_count, -m.max_violation_confidence)
