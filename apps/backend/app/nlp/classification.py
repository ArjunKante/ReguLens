"""Product category classification (Section 10).

Keyword-frequency classifier over title/brand/description/OCR text. This is
intentionally simple and auditable (a lookup table, not a trained model) so
an officer can see exactly why a category was suggested; it is always
presented as a suggestion the officer can override, and a manual override
always wins over the automated result (Section 10: "Manual category
selection must override low-confidence automated classification"), enforced
by the caller, not this module.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.enums import ProductCategoryCode

_KEYWORDS: dict[ProductCategoryCode, list[str]] = {
    ProductCategoryCode.FOOD: [
        "chips", "snack", "biscuit", "cookie", "chocolate", "candy", "juice", "milk",
        "atta", "flour", "rice", "oil", "spice", "masala", "tea", "coffee", "noodles",
        "namkeen", "sauce", "ketchup", "jam", "honey", "cereal", "oats", "bread",
        "paneer", "cheese", "butter", "ghee", "sugar", "salt", "pickle", "beverage",
        "drink", "soda", "water bottle", "food", "grocery", "dal", "pulses", "wheat",
        "namkeen", "sweet", "mithai", "bakery", "cake", "ice cream", "yogurt", "curd",
    ],
    ProductCategoryCode.COSMETIC_PERSONAL_CARE: [
        "soap", "shampoo", "conditioner", "cream", "lotion", "moisturizer", "toothpaste",
        "cosmetic", "deodorant", "perfume", "sunscreen", "serum", "lipstick", "makeup",
        "face wash", "body wash", "talcum powder", "hair oil", "skincare", "beauty",
        "razor", "shaving", "sanitary", "toothbrush", "mouthwash", "nail polish",
    ],
    ProductCategoryCode.HOUSEHOLD: [
        "cleaner", "detergent", "mop", "tissue", "dishwash", "phenyl", "freshener",
        "insecticide", "mosquito", "repellent", "toilet cleaner", "floor cleaner",
        "laundry", "fabric softener", "garbage bag", "scrub", "broom", "wiper",
        "air freshener", "disinfectant", "bleach",
    ],
}

_ALWAYS_LOW_CONFIDENCE = 0.35


@dataclass
class ClassificationResult:
    category: ProductCategoryCode
    confidence: float
    matched_keywords: list[str]


def classify_category(*text_fragments: str | None) -> ClassificationResult:
    text = " ".join(f for f in text_fragments if f).lower()
    if not text.strip():
        return ClassificationResult(ProductCategoryCode.UNKNOWN, 0.0, [])

    scores: dict[ProductCategoryCode, list[str]] = {cat: [] for cat in _KEYWORDS}
    for category, keywords in _KEYWORDS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                scores[category].append(kw)

    best_category = max(scores, key=lambda c: len(scores[c]))
    hit_count = len(scores[best_category])

    if hit_count == 0:
        return ClassificationResult(ProductCategoryCode.UNKNOWN, 0.1, [])

    other_hits = sum(len(v) for k, v in scores.items() if k != best_category)
    # Confidence grows with hit count and with how dominant the winning
    # category is relative to competing categories; capped well below 1.0
    # since this is a keyword heuristic, not a trained classifier.
    dominance = hit_count / (hit_count + other_hits) if (hit_count + other_hits) else 1.0
    confidence = min(0.55 + 0.1 * hit_count, 0.9) * dominance
    confidence = max(confidence, _ALWAYS_LOW_CONFIDENCE)

    return ClassificationResult(best_category, round(confidence, 2), scores[best_category])


_TOBACCO_KEYWORDS = ["tobacco", "cigarette", "bidi", "gutkha", "cigar", "khaini", "chewing tobacco", "zarda"]


def is_tobacco_product(*text_fragments: str | None) -> bool:
    """Used only by the Rule 26(a) small-package exemption gate, which does
    NOT apply to tobacco/tobacco products regardless of package size."""
    text = " ".join(f for f in text_fragments if f).lower()
    return any(kw in text for kw in _TOBACCO_KEYWORDS)
