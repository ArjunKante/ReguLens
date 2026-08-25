from __future__ import annotations

import uuid

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ProductCategoryCode
from app.models.mixins import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.inspection import Inspection


class ProductCategory(Base, UUIDPKMixin):
    __tablename__ = "product_categories"

    code: Mapped[ProductCategoryCode] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base, UUIDPKMixin, TimestampMixin):
    """A product entity resolved from a marketplace listing. Re-scans of the
    same URL attach new Inspection rows to the same Product so history is
    comparable across time (Section 31: caching / last_checked_at)."""

    __tablename__ = "products"

    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    platform: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    listed_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    mrp: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True, default="INR")

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_categories.id"), nullable=True
    )
    category_confidence: Mapped[float | None] = mapped_column(nullable=True)
    category_manually_overridden: Mapped[bool] = mapped_column(Boolean, default=False)

    last_checked_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    category: Mapped[ProductCategory | None] = relationship(back_populates="products")
    inspections: Mapped[list["Inspection"]] = relationship(back_populates="product")
