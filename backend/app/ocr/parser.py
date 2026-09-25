"""
Statutory physical markings detection parser for Legal Metrology compliance.
Detects physical non-retail, industrial, and export declarations from raw OCR text
with tolerance for ordinary OCR spacing, hyphenation, and punctuation variations.
DO NOT treat generic phrases such as 'institutional pack', 'industrial pack',
or 'export pack' as equivalent to statutory declarations.
"""
import re
from typing import Dict, Any, Optional

VALID_MARKET_CHANNELS = {
    "RETAIL",
    "INSTITUTIONAL",
    "INDUSTRIAL",
    "ECOMMERCE",
    "EXPORT",
    "UNKNOWN"
}

# Compiled regex patterns for statutory physical declarations
# Tolerant of spaces, hyphens, underscores, quotes, and punctuation variations
PATTERN_NOT_FOR_RETAIL_SALE = re.compile(
    r'(?i)\bnot[\s\-_"\'`]+for[\s\-_"\'`]+retail[\s\-_"\'`]+sale\b'
)
PATTERN_FOR_INDUSTRIAL_USE_ONLY = re.compile(
    r'(?i)\bfor[\s\-_"\'`]+industrial[\s\-_"\'`]+use[\s\-_"\'`]+only\b'
)
PATTERN_FOR_EXPORT_ONLY = re.compile(
    r'(?i)\bfor[\s\-_"\'`]+export[\s\-_"\'`]+only\b'
)


def normalize_market_channel(channel: Optional[str]) -> str:
    """
    Normalizes market channel input deterministically.
    Allowed canonical values: RETAIL, INSTITUTIONAL, INDUSTRIAL, ECOMMERCE, EXPORT, UNKNOWN.
    Invalid, unverified, or omitted input maps to 'UNKNOWN'.
    """
    if not channel or not isinstance(channel, str):
        return "UNKNOWN"
    cleaned = channel.strip().upper()
    if cleaned in {"E-COMMERCE", "E_COMMERCE", "ECOMMERCE"}:
        return "ECOMMERCE"
    if cleaned in VALID_MARKET_CHANNELS:
        return cleaned
    return "UNKNOWN"


def detect_statutory_physical_signals(text: Optional[str]) -> Dict[str, bool]:
    """
    Scans raw OCR text for statutory physical markings required for Legal Metrology
    applicability determination.

    Returns:
        Dict[str, bool] containing:
            - not_for_retail_sale_detected: bool
            - for_industrial_use_only_detected: bool
            - for_export_only_detected: bool
    """
    if not text or not isinstance(text, str):
        return {
            "not_for_retail_sale_detected": False,
            "for_industrial_use_only_detected": False,
            "for_export_only_detected": False
        }

    return {
        "not_for_retail_sale_detected": bool(PATTERN_NOT_FOR_RETAIL_SALE.search(text)),
        "for_industrial_use_only_detected": bool(PATTERN_FOR_INDUSTRIAL_USE_ONLY.search(text)),
        "for_export_only_detected": bool(PATTERN_FOR_EXPORT_ONLY.search(text))
    }
