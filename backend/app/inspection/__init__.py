"""
Inspection domain package for multi-image processing, OCR aggregation,
field-level provenance, and compliance lifecycle orchestration.
"""

from app.inspection.fusion import (
    normalize_mrp,
    normalize_quantity,
    normalize_unit_sale_price,
    normalize_date,
    normalize_text,
    values_equivalent,
    is_text_enrichment,
    EvidenceCandidate,
    EvidenceFusionResult,
    EvidenceFusionEngine
)

__all__ = [
    "normalize_mrp",
    "normalize_quantity",
    "normalize_unit_sale_price",
    "normalize_date",
    "normalize_text",
    "values_equivalent",
    "is_text_enrichment",
    "EvidenceCandidate",
    "EvidenceFusionResult",
    "EvidenceFusionEngine"
]
