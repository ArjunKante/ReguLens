"""Import every model module so SQLAlchemy's mapper registry is fully
populated (required for string-based relationship() references to resolve,
and for Alembic autogenerate to see every table)."""
from app.core.database import Base  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.batch import InspectionBatch  # noqa: F401
from app.models.compliance import ComplianceCheck, Evidence, Violation  # noqa: F401
from app.models.declaration import Declaration  # noqa: F401
from app.models.inspection import Inspection, InspectionSource, PipelineEvent  # noqa: F401
from app.models.product import Product, ProductCategory  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.review import ReviewDecision  # noqa: F401
from app.models.rules import Rule, RuleVersion  # noqa: F401
from app.models.scraping import OCRResult, ProductImage, WebExtraction, WebPage  # noqa: F401
from app.models.user import Role, User  # noqa: F401

__all__ = [
    "Base",
    "AuditLog",
    "InspectionBatch",
    "ComplianceCheck",
    "Evidence",
    "Violation",
    "Declaration",
    "Inspection",
    "InspectionSource",
    "PipelineEvent",
    "Product",
    "ProductCategory",
    "Report",
    "ReviewDecision",
    "Rule",
    "RuleVersion",
    "OCRResult",
    "ProductImage",
    "WebExtraction",
    "WebPage",
    "Role",
    "User",
]
