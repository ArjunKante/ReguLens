"""Product category classification tests (Section 10)."""
from __future__ import annotations

from app.models.enums import ProductCategoryCode
from app.nlp.classification import classify_category, is_institutional_or_industrial_context


def test_classifies_snack_as_food():
    result = classify_category("Tasty Munch Potato Chips 100g", "Tasty Munch", "Crunchy salted chips snack")
    assert result.category == ProductCategoryCode.FOOD
    assert result.confidence > 0.3


def test_classifies_shampoo_as_cosmetic_personal_care():
    result = classify_category("Glow Shampoo 200ml", "Glow", "Nourishing hair shampoo and conditioner")
    assert result.category == ProductCategoryCode.COSMETIC_PERSONAL_CARE


def test_classifies_floor_cleaner_as_household():
    result = classify_category("Shine Floor Cleaner 1L", "Shine", "Powerful disinfectant floor cleaner")
    assert result.category == ProductCategoryCode.HOUSEHOLD


def test_empty_text_yields_unknown_with_zero_confidence():
    result = classify_category(None, None, None)
    assert result.category == ProductCategoryCode.UNKNOWN
    assert result.confidence == 0.0


def test_no_keyword_match_yields_unknown_with_low_confidence():
    result = classify_category("Xyzzy Widget Model 42", "Xyzzy", "A generic mechanical part")
    assert result.category == ProductCategoryCode.UNKNOWN
    assert result.confidence < 0.5


def test_institutional_industrial_context_detected_from_explicit_listing_text():
    """Used only by the Rule 3 Chapter II applicability gate -- must fire
    only on an explicit self-description, never inferred from size/price."""
    assert is_institutional_or_industrial_context("Bulk Cleaning Solvent 30L - For Industrial Use Only")
    assert is_institutional_or_industrial_context("Catering Pack Rice 25kg", "Not for retail sale")


def test_institutional_industrial_context_absent_for_ordinary_listing():
    assert not is_institutional_or_industrial_context("Tasty Munch Potato Chips 100g", "Crunchy salted chips")
    assert not is_institutional_or_industrial_context(None, None)
