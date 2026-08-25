"""Seed roles and demo user accounts for local development / grading demos.

Run with:  python -m app.scripts.seed_demo_data

This creates one account per role with clearly-labeled demo credentials.
These are NOT production credentials — see docs/demo-guide.md. Running this
script twice is safe (idempotent — existing rows are left untouched).
"""
from __future__ import annotations

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.enums import RoleName
from app.models.product import ProductCategory
from app.models.user import Role, User

DEMO_USERS = [
    {
        "email": "admin@lmscan.demo",
        "password": "AdminDemo!2026",
        "full_name": "Demo Administrator",
        "role": RoleName.ADMIN,
    },
    {
        "email": "inspector@lmscan.demo",
        "password": "InspectorDemo!2026",
        "full_name": "Demo Inspector",
        "role": RoleName.INSPECTOR,
    },
    {
        "email": "reviewer@lmscan.demo",
        "password": "ReviewerDemo!2026",
        "full_name": "Demo Reviewer",
        "role": RoleName.REVIEWER,
    },
]

CATEGORY_SEED = [
    (
        "FOOD",
        "Food & Beverage",
        "Pre-packaged food/beverage commodities. Rule 6(1)(a) manufacturer/packer "
        "declaration is superseded by FSS Act labeling rules per Explanation III.",
    ),
    (
        "COSMETIC_PERSONAL_CARE",
        "Cosmetics & Personal Care",
        "Soaps, shampoos, toothpaste and similar toiletries; subject to the veg/non-veg "
        "dot declaration under Rule 6(1)(8) in addition to standard declarations.",
    ),
    (
        "HOUSEHOLD",
        "Household Products",
        "Cleaning agents, general household consumables not classified as food or cosmetics.",
    ),
    ("OTHER", "Other", "Packaged commodities that do not fit the above categories."),
    (
        "UNKNOWN",
        "Unknown / Unclassified",
        "Category could not be determined automatically; requires officer classification.",
    ),
]


def run() -> None:
    db = SessionLocal()
    try:
        for role_name in RoleName:
            existing = db.query(Role).filter(Role.name == role_name).one_or_none()
            if existing is None:
                db.add(Role(name=role_name))
        db.commit()

        for code, category_name, description in CATEGORY_SEED:
            existing_cat = (
                db.query(ProductCategory).filter(ProductCategory.code == code).one_or_none()
            )
            if existing_cat is None:
                db.add(ProductCategory(code=code, name=category_name, description=description))
        db.commit()

        for spec in DEMO_USERS:
            existing_user = db.query(User).filter(User.email == spec["email"]).one_or_none()
            if existing_user is not None:
                continue
            role = db.query(Role).filter(Role.name == spec["role"]).one()
            db.add(
                User(
                    email=spec["email"],
                    hashed_password=hash_password(spec["password"]),
                    full_name=spec["full_name"],
                    role_id=role.id,
                )
            )
        db.commit()
        print("Seed complete: roles, product categories, and demo users are present.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
