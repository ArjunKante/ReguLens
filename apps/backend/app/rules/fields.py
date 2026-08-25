"""The canonical vocabulary of declaration field names.

Both the declaration-extraction engine (app/nlp) and the rule seed data
(app/rules/seed_rules.py) import this module so the two sides can never
drift out of sync — a rule can only reference a field name that the
extraction engine actually knows how to produce.
"""
from __future__ import annotations

PRODUCT_NAME = "product_name"
MANUFACTURER_NAME = "manufacturer_name"
MANUFACTURER_ADDRESS = "manufacturer_address"
PACKER_NAME = "packer_name"
PACKER_ADDRESS = "packer_address"
IMPORTER_NAME = "importer_name"
IMPORTER_ADDRESS = "importer_address"
COUNTRY_OF_ORIGIN = "country_of_origin"
NET_QUANTITY = "net_quantity"
MRP = "mrp"
CONSUMER_CARE_NAME = "consumer_care_name"
CONSUMER_CARE_ADDRESS = "consumer_care_address"
CONSUMER_CARE_PHONE = "consumer_care_phone"
CONSUMER_CARE_EMAIL = "consumer_care_email"
MFG_DATE = "mfg_date"
BEST_BEFORE_DATE = "best_before_date"
UNIT_SALE_PRICE = "unit_sale_price"

ALL_FIELDS = [
    PRODUCT_NAME,
    MANUFACTURER_NAME,
    MANUFACTURER_ADDRESS,
    PACKER_NAME,
    PACKER_ADDRESS,
    IMPORTER_NAME,
    IMPORTER_ADDRESS,
    COUNTRY_OF_ORIGIN,
    NET_QUANTITY,
    MRP,
    CONSUMER_CARE_NAME,
    CONSUMER_CARE_ADDRESS,
    CONSUMER_CARE_PHONE,
    CONSUMER_CARE_EMAIL,
    MFG_DATE,
    BEST_BEFORE_DATE,
    UNIT_SALE_PRICE,
]

# Fields whose statutory basis (Rule 6(10)) requires them to be satisfied by a
# WEBPAGE_TEXT / STRUCTURED_METADATA source specifically — an image-only
# declaration does not, on its own, satisfy the e-commerce display duty.
ECOMMERCE_DISPLAY_FIELD_GROUPS: list[list[str]] = [
    [PRODUCT_NAME],
    [NET_QUANTITY],
    [MRP],
    [MANUFACTURER_NAME, PACKER_NAME, IMPORTER_NAME],
    [CONSUMER_CARE_NAME, CONSUMER_CARE_ADDRESS, CONSUMER_CARE_PHONE, CONSUMER_CARE_EMAIL],
]
