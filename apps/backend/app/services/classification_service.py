"""Applies the classification engine to a Product row, respecting manual
overrides (Section 10: "Manual category selection must override low-
confidence automated classification")."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.declaration import Declaration
from app.models.enums import ProductCategoryCode
from app.models.product import Product, ProductCategory
from app.nlp.classification import classify_category
from app.rules import fields as F


def get_or_create_category(db: Session, code: ProductCategoryCode) -> ProductCategory:
    category = db.query(ProductCategory).filter(ProductCategory.code == code.value).one_or_none()
    if category is None:
        category = ProductCategory(code=code.value, name=code.value.replace("_", " ").title())
        db.add(category)
        db.commit()
        db.refresh(category)
    return category


def classify_product(db: Session, product: Product, ocr_text_fragments: list[str]) -> ProductCategoryCode:
    """Returns the category actually in effect after classification —
    either the freshly-classified one, or the existing manual override."""
    if product.category_manually_overridden and product.category is not None:
        return ProductCategoryCode(product.category.code)

    generic_name_decl = (
        db.query(Declaration)
        .filter(Declaration.inspection_id.in_([i.id for i in product.inspections]), Declaration.field_name == F.PRODUCT_NAME)
        .order_by(Declaration.confidence.desc())
        .first()
    ) if product.inspections else None

    result = classify_category(
        product.title,
        product.brand,
        product.description,
        generic_name_decl.value if generic_name_decl else None,
        *ocr_text_fragments,
    )

    category_row = get_or_create_category(db, result.category)
    product.category_id = category_row.id
    product.category_confidence = result.confidence
    db.commit()
    return result.category
