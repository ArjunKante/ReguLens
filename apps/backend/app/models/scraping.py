from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EvidenceSourceType, ExtractionStrategy, WebFetchStatus
from app.models.mixins import UUIDPKMixin

if TYPE_CHECKING:
    from app.models.inspection import Inspection


class WebPage(Base, UUIDPKMixin):
    """One fetch attempt of a marketplace product page."""

    __tablename__ = "web_pages"

    inspection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspections.id"), nullable=False)

    url: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str | None] = mapped_column(String(64), nullable=True)

    fetch_status: Mapped[WebFetchStatus] = mapped_column(String(32), nullable=False)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # True when the HTTP fetch itself succeeded but the page yielded no real
    # product data (e.g. a marketplace serving its generic app-shell/homepage
    # instead of the actual listing — see services/pipeline.py's hollow-
    # success detection). Kept separate from fetch_status, which stays an
    # honest record of what actually happened at the HTTP layer — this flag
    # is what tells the compliance engine (app/compliance/context.py) not to
    # treat a hollow "success" as real evidence when scoring evidence
    # quality, so a failed/gated scrape reports UNABLE_TO_VERIFY/
    # NEEDS_MANUAL_REVIEW rather than a confident POTENTIAL_NON_COMPLIANCE
    # against data that was never actually retrieved.
    hollow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    robots_txt_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    robots_txt_checked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scraper_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scraper_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    page_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    raw_html_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    inspection: Mapped["Inspection"] = relationship(back_populates="web_pages")
    extractions: Mapped[list["WebExtraction"]] = relationship(
        back_populates="web_page", cascade="all, delete-orphan"
    )


class WebExtraction(Base, UUIDPKMixin):
    """One raw field extracted from a web page by one extraction strategy,
    before consolidation into the unified `declarations` table. Kept
    separate so multiple strategies can disagree and that disagreement is
    itself visible (Section 3/27: never rely on a single CSS selector)."""

    __tablename__ = "web_extractions"

    web_page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("web_pages.id"), nullable=False)
    strategy: Mapped[ExtractionStrategy] = mapped_column(String(32), nullable=False)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    field_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    raw_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    web_page: Mapped[WebPage] = relationship(back_populates="extractions")


class ProductImage(Base, UUIDPKMixin):
    __tablename__ = "product_images"

    inspection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspections.id"), nullable=False)
    source_type: Mapped[EvidenceSourceType] = mapped_column(String(32), nullable=False)

    original_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_blurry: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    blur_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    contrast_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    glare_detected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    quality_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_acceptable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    downloaded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    inspection: Mapped["Inspection"] = relationship(back_populates="images")
    ocr_results: Mapped[list["OCRResult"]] = relationship(
        back_populates="product_image", cascade="all, delete-orphan"
    )


class OCRResult(Base, UUIDPKMixin):
    """One raw OCR text block. Low-confidence results are stored, never
    discarded (Section 7), so an officer can see exactly what the OCR
    engine produced and why the system's confidence was low."""

    __tablename__ = "ocr_results"

    product_image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_images.id"), nullable=False)

    engine: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bounding_box: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {x,y,w,h} in pixels

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    product_image: Mapped[ProductImage] = relationship(back_populates="ocr_results")
