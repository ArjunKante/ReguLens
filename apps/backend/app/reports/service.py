"""Renders and persists inspection reports (Section 17)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session
from xhtml2pdf import pisa

from app.models.inspection import Inspection
from app.models.report import Report
from app.models.user import User
from app.reports.context import build_report_context
from app.storage.files import save_report_bytes

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "j2"]),
)


def render_report_html(inspection: Inspection, generated_by_name: str) -> str:
    ctx = build_report_context(inspection, generated_by_name)
    template = _env.get_template("inspection_report.html.j2")
    return template.render(ctx=ctx)


def html_to_pdf_bytes(html: str) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    result = pisa.CreatePDF(src=html, dest=buffer, encoding="utf-8")
    if result.err:
        raise RuntimeError("PDF generation failed.")
    return buffer.getvalue()


def generate_report(db: Session, inspection: Inspection, generated_by: User, fmt: str = "PDF") -> Report:
    html = render_report_html(inspection, generated_by.full_name)

    if fmt == "PDF":
        content = html_to_pdf_bytes(html)
        extension = "pdf"
    else:
        content = html.encode("utf-8")
        extension = "html"

    file_path = save_report_bytes(inspection.id, content, extension=extension)

    ctx = build_report_context(inspection, generated_by.full_name)
    report = Report(
        inspection_id=inspection.id,
        generated_by_id=generated_by.id,
        format=fmt,
        file_path=file_path,
        rule_version_snapshot={"rules": ctx.rule_version_snapshot},
        generated_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
