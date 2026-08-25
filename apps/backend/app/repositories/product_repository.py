from __future__ import annotations

import datetime as dt
import hashlib

from sqlalchemy.orm import Session

from app.models.product import Product


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()


def get_or_create_product(db: Session, url: str, platform: str | None) -> Product:
    h = url_hash(url)
    product = db.query(Product).filter(Product.url_hash == h).one_or_none()
    if product is None:
        product = Product(canonical_url=url, url_hash=h, platform=platform)
        db.add(product)
        db.commit()
        db.refresh(product)
    return product


def touch_last_checked(db: Session, product: Product) -> None:
    product.last_checked_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
