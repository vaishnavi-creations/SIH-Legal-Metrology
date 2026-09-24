import re
import unicodedata
import logging
from pydantic import BaseModel, Field
from typing import Optional, Tuple, Any, Union, List, Dict

from app.extractor.gemini_parser import _devanagari_to_ascii_digits, DEV_UNIT_MAP
from app.schemas.inspection import EvidenceSource, FieldConflict, FieldProvenance
from app.schemas.ocr import OCRResult
from app.ocr.script_detector import ScriptDetector
from app.schemas.product import (
    StructuredProductData,
    MRPDetails,
    NetQuantityDetails,
    DateDetails,
    UnitSalePriceDetails,
    ManufacturerDetails,
    ConsumerCareDetails
)

logger = logging.getLogger(__name__)

# Standard metric conversion factors to canonical base units
METRIC_MASS_FACTORS = {
    "g": 1.0,
    "gm": 1.0,
    "gms": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1000.0,
    "kilo": 1000.0,
    "kilogram": 1000.0,
    "mg": 0.001,
}

METRIC_VOLUME_FACTORS = {
    "ml": 1.0,
    "l": 1000.0,
    "litre": 1000.0,
    "liter": 1000.0,
    "litres": 1000.0,
    "liters": 1000.0,
    "ltr": 1000.0,
    "ltrs": 1000.0,
    "kl": 1000000.0,
}

METRIC_LENGTH_FACTORS = {
    "cm": 1.0,
    "m": 100.0,
    "mm": 0.1,
}

COUNT_UNITS = {
    "pcs", "pieces", "units", "u", "n", "number", "piece",
    "नग", "पीस", "गोलियां", "इकाइयां"
}

MONTH_NAME_MAP = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12"
}


def normalize_mrp(val: Any) -> Optional[float]:
    """
    Normalizes Maximum Retail Price declarations into a comparable float value.
    Strips currency symbols (₹, Rs, INR), tax statements, and surrounding punctuation.
    Supports Devanagari numerals.
    Never invents missing values; returns None if no valid price digits are found.
    """
    if val is None:
        return None

    if isinstance(val, MRPDetails):
        if val.value is not None:
            return round(float(val.value), 2)
        val = val.raw_text

    if isinstance(val, (int, float)):
        return round(float(val), 2)

    if not isinstance(val, str):
        return None

    text = val.strip()
    if not text:
        return None

    # Convert Devanagari numerals
    text = _devanagari_to_ascii_digits(text)

    # Check for corrupted strings where characters are mixed into numbers or isolated header
    # Strip common prefixes/headers
    text = re.sub(
        r'(?i)\b(?:MRP|M\.R\.P|Retail\s*Price|Maximum\s*Retail\s*Price)\b|'
        r'अधिकतम\s*(?:खुदरा\s*)?मूल्य|अधिकतमखुदरामूल्य|खुदरा\s*मूल्य|मूल्य',
        '',
        text
    ).strip()

    # Strip currency symbols and tax phrases
    text = re.sub(r'(?i)[₹]|Rs\.?|INR|रु\.?|रुपये|रुपए', '', text)
    text = re.sub(r'(?i)\(?\s*(?:incl\.?|inclusive)?\s*(?:of)?\s*(?:all)?\s*taxes\s*\)?', '', text)
    text = re.sub(r'(?i)\(?\s*सभी\s*करों\s*सहित\s*\)?', '', text)

    # Clean whitespace and surrounding punctuation
    text = text.strip(" :.-=/,\t\n\r")
    if not text:
        return None

    # Guard against phone/contact numbers being mistaken for MRP (e.g. 1800-xxx-xxxx, 1800 444 5555, +91-xxx)
    if re.search(r'(?i)\b(?:toll\s*free|phone|tel|helpline|call|contact|mobile)\b|1800[-\s]?[0-9]{3}|\+91[-\s]?[0-9]{5}', text):
        return None
    if re.match(r'^[0-9]{3,5}[-\s][0-9]{3,4}[-\s]?[0-9]{3,4}$', text) or re.match(r'^\+91[-\s]?[0-9]{10}$', text):
        return None

    # Guard against batch / lot numbers being mistaken for MRP (e.g. Batch No: 1234, Lot 5678)
    if re.search(r'(?i)\b(?:batch|lot|b\.?\s*no|lot\.?\s*no)\b', text):
        return None

    # Match numeric price pattern
    match = re.search(r'\b([0-9]+(?:\.[0-9]{1,2})?)\b', text)
    if not match:
        return None

    try:
        parsed = float(match.group(1))
        return round(parsed, 2)
    except (ValueError, TypeError):
        return None


def normalize_quantity(val: Any) -> Optional[Tuple[float, str]]:
    """
    Normalizes Net Quantity declarations into a canonical tuple of (base_value, canonical_unit).
    Metric units are normalized to base representations:
      - Mass/weight -> 'g' (e.g. 0.5 kg -> 500.0 g)
      - Volume -> 'ml' (e.g. 1 l -> 1000.0 ml)
    Count/piece declarations remain count-based ('pcs') and are NEVER converted to metric mass/volume.
    Supports Hindi metric units (ग्राम, किग्रा, मिली, etc.).
    Returns None if quantity or unit cannot be deterministically resolved.
    """
    if val is None:
        return None

    num_val: Optional[float] = None
    unit_str: Optional[str] = None

    if isinstance(val, NetQuantityDetails):
        if val.value is not None and val.unit:
            num_val = float(val.value)
            unit_str = val.unit.strip().lower()
        elif val.piece_count is not None:
            return (float(val.piece_count), "pcs")
        elif val.raw_text:
            val = val.raw_text
        else:
            return None

    if isinstance(val, (tuple, list)) and len(val) >= 2:
        try:
            num_val = float(_devanagari_to_ascii_digits(str(val[0])))
            unit_str = str(val[1]).strip().lower()
        except (ValueError, TypeError):
            return None

    elif isinstance(val, str):
        text = _devanagari_to_ascii_digits(val.strip())
        # Strip Net Qty keyword wrappers
        text = re.sub(
            r'(?i)\b(?:Net\s*(?:Quantity|Qty|Weight|Wt\.?)|Net)\b|'
            r'शुद्ध\s*मात्रा|शुद्धमात्रा|मात्रा|कुल\s*मात्रा',
            '',
            text
        ).strip(" :.-=/\t\n\r")

        # Map Devanagari unit terms if present (longest first to prevent subphrase preemption)
        for dev_u in sorted(DEV_UNIT_MAP.keys(), key=len, reverse=True):
            if dev_u in text:
                text = text.replace(dev_u, f" {DEV_UNIT_MAP[dev_u]} ")
                break

        # Check for count declarations (e.g. 10 pieces, 10 नग)
        piece_match = re.search(
            r'\b([0-9]+)\s*(?:pcs|pieces|units|tablets|capsules|n|u|number|नग|पीस|गोलियां|इकाइयां)\b',
            text,
            re.IGNORECASE
        )
        if piece_match:
            try:
                return (float(piece_match.group(1)), "pcs")
            except (ValueError, TypeError):
                pass

        # Match metric quantity pattern: number followed by unit word
        metric_match = re.search(r'\b([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)\b', text)
        if metric_match:
            try:
                num_val = float(metric_match.group(1))
                unit_str = metric_match.group(2).lower()
            except (ValueError, TypeError):
                return None
        else:
            return None

    if num_val is None or unit_str is None:
        return None

    # Normalize unit through DEV_UNIT_MAP if applicable
    unit_clean = DEV_UNIT_MAP.get(unit_str, unit_str).lower()

    # Canonicalize to base metric units
    if unit_clean in METRIC_MASS_FACTORS:
        base_val = num_val * METRIC_MASS_FACTORS[unit_clean]
        return (round(base_val, 4), "g")

    if unit_clean in METRIC_VOLUME_FACTORS:
        base_val = num_val * METRIC_VOLUME_FACTORS[unit_clean]
        return (round(base_val, 4), "ml")

    if unit_clean in METRIC_LENGTH_FACTORS:
        base_val = num_val * METRIC_LENGTH_FACTORS[unit_clean]
        return (round(base_val, 4), "cm")

    if unit_clean in COUNT_UNITS:
        return (round(num_val, 4), "pcs")

    return (round(num_val, 4), unit_clean)


def normalize_unit_sale_price(val: Any) -> Optional[Tuple[float, str]]:
    """
    Normalizes Unit Sale Price declarations into a canonical tuple of (price_per_base_unit, base_unit).
    Examples:
      - '₹0.50 / g' -> (0.5, 'g')
      - 'Rs. 0.50/g' -> (0.5, 'g')
      - '0.50 प्रति ग्राम' -> (0.5, 'g')
      - 'Rs. 500 / kg' -> (0.5, 'g')
    Returns None if price or unit cannot be resolved.
    """
    if val is None:
        return None

    price: Optional[float] = None
    unit_str: Optional[str] = None

    if isinstance(val, UnitSalePriceDetails):
        if val.value is not None and val.unit:
            price = float(val.value)
            unit_str = val.unit
        elif val.raw_text:
            val = val.raw_text
        else:
            return None

    if isinstance(val, (tuple, list)) and len(val) >= 2:
        try:
            price = float(_devanagari_to_ascii_digits(str(val[0])))
            unit_str = str(val[1]).strip().lower()
        except (ValueError, TypeError):
            return None

    elif isinstance(val, str):
        text = _devanagari_to_ascii_digits(val.strip())

        # Strip USP headers
        text = re.sub(
            r'(?i)\b(?:Unit\s*Sale\s*Price|USP)\b|'
            r'इकाई\s*(?:बिक्री\s*)?मूल्य|इकाई\s*मूल्य|प्रति\s*इकाई\s*मूल्य',
            '',
            text
        ).strip(" :.-=\t\n\r")

        # Map Devanagari units (longest first to prevent subphrase preemption)
        for dev_u in sorted(DEV_UNIT_MAP.keys(), key=len, reverse=True):
            if dev_u in text:
                text = text.replace(dev_u, DEV_UNIT_MAP[dev_u])

        # Strip currency symbols
        text = re.sub(r'(?i)[₹]|Rs\.?|INR|रु\.?', '', text)

        # Replace 'per' or 'प्रति' with '/'
        text = re.sub(r'(?i)\bper\b|प्रति', '/', text)

        match = re.search(
            r'([0-9]+(?:\.[0-9]+)?)\s*(?:\/|\s*per\s*|\s*प्रति\s*)\s*([0-9]*)\s*([a-zA-Z]+)',
            text
        )
        if match:
            try:
                price = float(match.group(1))
                multiplier_str = match.group(2).strip()
                multiplier = float(multiplier_str) if multiplier_str else 1.0
                raw_u = match.group(3).strip().lower()
                unit_clean = DEV_UNIT_MAP.get(raw_u, raw_u)
                if multiplier > 1.0:
                    unit_str = f"{int(multiplier)} {unit_clean}"
                else:
                    unit_str = unit_clean
            except (ValueError, TypeError):
                return None
        else:
            return None

    if price is None or unit_str is None:
        return None

    unit_clean = unit_str.strip().lower()
    # Normalize unit multiplier if present (e.g. '100 g', '1 kg')
    multiplier = 1.0
    mult_match = re.match(r'^([0-9]+)\s*([a-zA-Z]+)$', unit_clean)
    if mult_match:
        multiplier = float(mult_match.group(1))
        unit_clean = mult_match.group(2).lower()

    unit_clean = DEV_UNIT_MAP.get(unit_clean, unit_clean)

    # Normalize to base units
    if unit_clean in METRIC_MASS_FACTORS:
        factor = METRIC_MASS_FACTORS[unit_clean] * multiplier
        price_per_base = price / factor
        return (round(price_per_base, 6), "g")

    if unit_clean in METRIC_VOLUME_FACTORS:
        factor = METRIC_VOLUME_FACTORS[unit_clean] * multiplier
        price_per_base = price / factor
        return (round(price_per_base, 6), "ml")

    if unit_clean in COUNT_UNITS:
        return (round(price / multiplier, 6), "pcs")

    return (round(price, 6), unit_clean)


def normalize_date(val: Any) -> Optional[str]:
    """
    Normalizes manufacturing/packaging/expiry dates into a standardized string format.
    Standardizes equivalent month/year representations:
      - '08/2026' == '08-2026' -> '08/2026'
      - 'August 2026' == 'Aug 2026' -> '08/2026'
    Never invents missing dates or guesses ambiguous strings without separators (e.g. '0612026' -> None).
    """
    if val is None:
        return None

    if isinstance(val, DateDetails):
        val = val.manufacturing_date or val.packaging_date or val.packing_date or val.expiry_date or val.raw_text

    if not isinstance(val, str):
        return None

    text = _devanagari_to_ascii_digits(val.strip())
    if not text:
        return None

    # Strip declaration keywords
    text = re.sub(
        r'(?i)\b(?:Mfg|Manufacture|Manufactured|Pkd|Packed|Packing|Imported|Import|Best\s*Before|Expiry|Exp\.?\s*Date)\b|'
        r'निर्माण\s*(?:तिथि|तारीख)?|निर्माणतिथि|पैकिंग\s*(?:तिथि|तारीख)?|पैकिंगतिथि',
        '',
        text
    ).strip(" :.-=\t\n\r")

    # Match standard DD/MM/YYYY or DD-MM-YYYY
    full_date_match = re.search(
        r'\b(0?[1-9]|[12][0-9]|3[01])[\/\-\.](0?[1-9]|1[0-2])[\/\-\.](20[0-9]{2}|19[0-9]{2})\b',
        text
    )
    if full_date_match:
        d, m, y = full_date_match.groups()
        return f"{int(d):02d}/{int(m):02d}/{y}"

    # Match standard MM/YYYY or MM-YYYY
    my_match = re.search(
        r'\b(0?[1-9]|1[0-2])[\/\-\.](20[0-9]{2}|19[0-9]{2})\b',
        text
    )
    if my_match:
        m, y = my_match.groups()
        return f"{int(m):02d}/{y}"

    # Match Month Name + Year (e.g. 'August 2026', 'Aug-2026')
    month_name_match = re.search(
        r'\b([A-Za-z]{3,9})[\s\/\-\.](20[0-9]{2}|19[0-9]{2})\b',
        text
    )
    if month_name_match:
        m_name = month_name_match.group(1).lower()
        y = month_name_match.group(2)
        if m_name in MONTH_NAME_MAP:
            return f"{MONTH_NAME_MAP[m_name]}/{y}"

    return None


def normalize_text(val: Any) -> Optional[str]:
    """
    Conservative string normalization for textual fields:
    - Unicode normalization (NFKC)
    - Whitespace normalization (collapses multiple spaces, strips ends)
    - Case normalization (lowercase)
    - Safe punctuation normalization (strips edge punctuation and quotes)
    Does NOT use aggressive fuzzy matching.
    Does NOT merge distinct company or product names.
    """
    if val is None:
        return None

    if isinstance(val, (ManufacturerDetails, ConsumerCareDetails)):
        val = getattr(val, "name", None) or getattr(val, "raw_text", None)

    if not isinstance(val, str):
        val = str(val)

    # Unicode NFKC normalization
    text = unicodedata.normalize("NFKC", val)

    # Replace newlines, tabs, and multiple spaces with a single space
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Case normalization
    text = text.lower()

    # Strip surrounding quotes and punctuation
    text = text.strip(" .,;:!?'\"`~-_/\\()[]{}|")

    if not text:
        return None

    return text


def values_equivalent(val1: Any, val2: Any, field_type: str = "auto") -> bool:
    """
    Deterministic equivalence check between two pieces of evidence for the same field.
    Returns True ONLY if both values normalize to the same canonical representation.
    Returns False if either value is None, invalid, or contradictory.
    Never chooses a winner or resolves conflicts.
    """
    if val1 is None or val2 is None:
        return False

    ft = field_type.lower() if field_type else "auto"

    # Auto-detect field type from input objects if requested
    if ft == "auto":
        if isinstance(val1, MRPDetails) or isinstance(val2, MRPDetails):
            ft = "mrp"
        elif isinstance(val1, NetQuantityDetails) or isinstance(val2, NetQuantityDetails):
            ft = "net_quantity"
        elif isinstance(val1, DateDetails) or isinstance(val2, DateDetails):
            ft = "date"
        elif isinstance(val1, UnitSalePriceDetails) or isinstance(val2, UnitSalePriceDetails):
            ft = "unit_sale_price"
        elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            return abs(float(val1) - float(val2)) < 0.001

    if ft in ("mrp", "price"):
        n1 = normalize_mrp(val1)
        n2 = normalize_mrp(val2)
        if n1 is None or n2 is None:
            return False
        return abs(n1 - n2) < 0.01

    if ft in ("net_quantity", "quantity"):
        n1 = normalize_quantity(val1)
        n2 = normalize_quantity(val2)
        if n1 is None or n2 is None:
            return False
        v1, u1 = n1
        v2, u2 = n2
        return u1 == u2 and abs(v1 - v2) < 0.001

    if ft in ("unit_sale_price", "usp"):
        n1 = normalize_unit_sale_price(val1)
        n2 = normalize_unit_sale_price(val2)
        if n1 is None or n2 is None:
            return False
        p1, u1 = n1
        p2, u2 = n2
        return u1 == u2 and abs(p1 - p2) < 0.0001

    if ft in ("date", "dates", "manufacturing_date", "packaging_date", "expiry_date"):
        n1 = normalize_date(val1)
        n2 = normalize_date(val2)
        if n1 is None or n2 is None:
            return False
        return n1 == n2

    # Default to conservative text normalization
    n1 = normalize_text(val1)
    n2 = normalize_text(val2)
    if n1 is None or n2 is None:
        return False
    return n1 == n2


def is_text_enrichment(text1: Any, text2: Any) -> bool:
    """
    Checks if one entity/address string is a natural enrichment of another
    (e.g. 'ABC Foods' vs 'ABC Foods Pvt Ltd, Plot 10, Pune 411001').
    Returns True if one normalized string is contained within the other.
    Returns False if they are distinct or contradictory entities.
    """
    if text1 is None or text2 is None:
        return False
    n1 = normalize_text(text1)
    n2 = normalize_text(text2)
    if not n1 or not n2:
        return False
    return n1 in n2 or n2 in n1


class EvidenceCandidate(BaseModel):
    """
    Represents an atomic, field-level declaration extracted from a specific packaging image view.
    """
    field_name: str = Field(..., description="Target statutory field (e.g. mrp, net_quantity, manufacturer)")
    extracted_value: Any = Field(..., description="Raw or parsed declaration value")
    source_image_id: Optional[int] = Field(None, description="Database ID of the originating image")
    source_role: Optional[str] = Field(None, description="Package view role (front, back, label, etc.)")
    source_sequence: Optional[int] = Field(None, description="Display sequence index of the source image")
    source_text: Optional[str] = Field(None, description="Exact OCR snippet from which declaration was extracted")
    confidence: Optional[float] = Field(None, description="Confidence of detection if measured")
    detected_script: Optional[str] = Field(None, description="Script of originating text (LATIN, DEVANAGARI, etc.)")

    def to_evidence_source(self) -> EvidenceSource:
        val = self.extracted_value
        if isinstance(val, BaseModel):
            val = val.model_dump()
        return EvidenceSource(
            source_image_id=self.source_image_id,
            source_role=self.source_role,
            source_sequence=self.source_sequence,
            source_text=self.source_text,
            confidence=self.confidence,
            detected_script=self.detected_script,
            extracted_value=val
        )


class EvidenceFusionResult(BaseModel):
    """
    Output of EvidenceFusionEngine reconciling declarations across all packaging views.
    """
    structured_data: StructuredProductData
    provenance: Dict[str, Optional[FieldProvenance]]
    conflicts: List[FieldConflict] = Field(default_factory=list)
    is_conflicted: bool = False


class EvidenceFusionEngine:
    """
    Reconciles field-level packaging declarations across multiple image views.
    Performs:
    1. Per-field evidence candidate collection
    2. Cross-image corroboration (matching declarations confirmed by 2+ views)
    3. Cross-image conflict detection (contradictory declarations flagged without picking arbitrary winners)
    4. Complementary evidence synthesis (combining distinct declarations across views)
    5. Multi-source provenance tracking (linking declarations to all supporting or competing views)
    """

    SUPPORTED_FIELDS: List[str] = [
        "product_name",
        "common_or_generic_name",
        "mrp",
        "net_quantity",
        "unit_sale_price",
        "dates",
        "manufacturer",
        "consumer_care",
        "country_of_origin"
    ]

    @classmethod
    def fuse(cls, candidates: List[EvidenceCandidate]) -> EvidenceFusionResult:
        structured = StructuredProductData(
            extraction_method="evidence_fusion",
            extraction_confidence=0.95
        )
        provenance: Dict[str, Optional[FieldProvenance]] = {}
        all_conflicts: List[FieldConflict] = []
        is_inspection_conflicted = False

        for field in cls.SUPPORTED_FIELDS:
            # 1. Filter candidates for current field with non-None values
            raw_cands = [c for c in candidates if c.field_name == field and c.extracted_value is not None]

            # 2. Validate candidates according to field-specific normalization rules
            valid_cands: List[EvidenceCandidate] = []
            for c in raw_cands:
                val = c.extracted_value
                if field == "mrp" and normalize_mrp(val) is None:
                    continue
                if field == "net_quantity" and normalize_quantity(val) is None:
                    continue
                if field == "unit_sale_price" and normalize_unit_sale_price(val) is None:
                    continue
                if field == "dates" and normalize_date(val) is None and (isinstance(val, str) and not val.strip()):
                    continue
                if field == "product_name":
                    if not normalize_text(val):
                        continue
                    if re.search(r'(?i)^(?:MRP|Net|Pkg|Mfg|Consumer|Best|Batch|Country|Unit|कारखाना|पता|पंजीकृत|निर्माता|उपभोक्ता|अधिकतम|शुद्ध)', str(val).strip()):
                        continue
                elif field in ("common_or_generic_name", "manufacturer", "consumer_care", "country_of_origin"):
                    if not normalize_text(val):
                        continue
                valid_cands.append(c)

            if not valid_cands:
                # Preserve raw text snippet if declaration was detected on a packaging view
                # but without a valid or unambiguous numeric value (e.g. Devanagari "शुद्ध मात्रा")
                raw_with_text = [
                    c for c in raw_cands
                    if c.source_text and re.search(r'(?i)net|qty|weight|wt|शुद्ध|मात्रा', c.source_text)
                ]
                if raw_with_text and field == "net_quantity":
                    primary_raw = raw_with_text[0]
                    structured.net_quantity.raw_text = primary_raw.source_text
                    structured.net_quantity.value = None
                    prov = FieldProvenance(
                        value=None,
                        source_image_id=primary_raw.source_image_id,
                        source_role=primary_raw.source_role,
                        source_sequence=primary_raw.source_sequence,
                        source_text=primary_raw.source_text,
                        confidence=primary_raw.confidence,
                        detected_script=primary_raw.detected_script,
                        is_corroborated=False,
                        corroborating_sources=[c.to_evidence_source() for c in raw_with_text],
                        has_conflict=False,
                        conflicts=[]
                    )
                    provenance[field] = prov
                else:
                    provenance[field] = None
                continue

            # 3. Cluster equivalent candidates
            clusters: List[List[EvidenceCandidate]] = []
            for cand in valid_cands:
                matched = False
                for cluster in clusters:
                    if values_equivalent(cand.extracted_value, cluster[0].extracted_value, field_type=field):
                        cluster.append(cand)
                        matched = True
                        break
                if not matched:
                    clusters.append([cand])

            # 4. Check for manufacturer / entity enrichment
            is_enriched = False
            if field in ("manufacturer", "product_name") and len(clusters) > 1:
                all_enriching = True
                base_text = str(clusters[0][0].extracted_value)
                for cl in clusters[1:]:
                    cand_text = str(cl[0].extracted_value)
                    if not is_text_enrichment(base_text, cand_text):
                        all_enriching = False
                        break
                if all_enriching:
                    merged = [c for cl in clusters for c in cl]
                    # Sort by text length descending so richer details are primary
                    merged.sort(key=lambda c: len(str(c.extracted_value)), reverse=True)
                    clusters = [merged]
                    is_enriched = True

            # 5. Evaluate consensus vs conflict
            if len(clusters) == 1:
                cluster = clusters[0]
                primary_cand = cluster[0]
                sources = [c.to_evidence_source() for c in cluster]
                is_corroborated = (len(cluster) >= 2 and not is_enriched)

                prov_val = primary_cand.extracted_value
                if isinstance(prov_val, ManufacturerDetails):
                    prov_val = prov_val.name or prov_val.raw_text or str(prov_val)
                elif isinstance(prov_val, ConsumerCareDetails):
                    prov_val = prov_val.phone or prov_val.email or prov_val.raw_text or str(prov_val)
                elif isinstance(prov_val, DateDetails):
                    prov_val = prov_val.manufacturing_date or prov_val.packaging_date or prov_val.best_before or str(prov_val)
                elif isinstance(prov_val, MRPDetails):
                    prov_val = prov_val.value if prov_val.value is not None else prov_val.raw_text
                elif isinstance(prov_val, NetQuantityDetails):
                    prov_val = prov_val.value if prov_val.value is not None else prov_val.piece_count

                prov = FieldProvenance(
                    value=prov_val,
                    source_image_id=primary_cand.source_image_id,
                    source_role=primary_cand.source_role,
                    source_sequence=primary_cand.source_sequence,
                    source_text=primary_cand.source_text,
                    is_corroborated=is_corroborated,
                    corroborating_sources=sources,
                    has_conflict=False,
                    conflicts=[]
                )
                provenance[field] = prov

                # Populate consolidated StructuredProductData
                cls._populate_field(structured, field, primary_cand, cluster)

            else:
                # Conflict detected across 2+ competing clusters
                competing_values = [
                    cl[0].extracted_value.model_dump() if isinstance(cl[0].extracted_value, BaseModel)
                    else cl[0].extracted_value
                    for cl in clusters
                ]
                all_sources = [c.to_evidence_source() for cl in clusters for c in cl]
                field_conflict = FieldConflict(
                    field_name=field,
                    competing_values=competing_values,
                    sources=all_sources,
                    conflict_type="VALUE_MISMATCH"
                )
                all_conflicts.append(field_conflict)
                is_inspection_conflicted = True

                prov = FieldProvenance(
                    value=None,
                    source_image_id=None,
                    source_role=None,
                    source_sequence=None,
                    source_text=None,
                    is_corroborated=False,
                    corroborating_sources=all_sources,
                    has_conflict=True,
                    conflicts=[field_conflict]
                )
                provenance[field] = prov
                # Scalar value in structured is intentionally left unset (None)

        # Check if any candidate has batch_number
        batch_cands = [c for c in candidates if c.field_name == "batch_number" and c.extracted_value]
        if batch_cands and not structured.batch_number:
            structured.batch_number = str(batch_cands[0].extracted_value)

        return EvidenceFusionResult(
            structured_data=structured,
            provenance=provenance,
            conflicts=all_conflicts,
            is_conflicted=is_inspection_conflicted
        )

    @classmethod
    def _populate_field(
        cls,
        structured: StructuredProductData,
        field: str,
        primary_cand: EvidenceCandidate,
        cluster: List[EvidenceCandidate]
    ) -> None:
        val = primary_cand.extracted_value
        raw_text = primary_cand.source_text or str(val)

        if field == "mrp":
            norm_val = normalize_mrp(val)
            structured.mrp.value = norm_val
            structured.mrp.raw_text = raw_text
            structured.mrp.currency = "INR"
            if any(re.search(r'(?i)incl|कर.*सहित', c.source_text or "") for c in cluster):
                structured.mrp.includes_taxes = True
            if isinstance(val, MRPDetails) and val.unit_sale_price and not structured.mrp.unit_sale_price:
                structured.mrp.unit_sale_price = val.unit_sale_price

        elif field == "net_quantity":
            norm_q = normalize_quantity(val)
            if norm_q:
                val_num, unit = norm_q
                if unit == "pcs":
                    structured.net_quantity.piece_count = int(val_num)
                    structured.net_quantity.unit = "pcs"
                else:
                    structured.net_quantity.value = val_num
                    structured.net_quantity.unit = unit
            structured.net_quantity.raw_text = raw_text

        elif field == "unit_sale_price":
            norm_usp = normalize_unit_sale_price(val)
            if norm_usp:
                price_val, usp_unit = norm_usp
                structured.unit_sale_price = UnitSalePriceDetails(
                    raw_text=raw_text,
                    value=price_val,
                    unit=usp_unit,
                    currency="INR"
                )
                structured.mrp.unit_sale_price = f"Rs. {price_val} / {usp_unit}"

        elif field == "dates":
            dates_objs = [c.extracted_value for c in cluster if isinstance(c.extracted_value, DateDetails)]
            if dates_objs:
                merged_dates = DateDetails()
                for d in dates_objs:
                    if d.manufacturing_date and not merged_dates.manufacturing_date:
                        merged_dates.manufacturing_date = d.manufacturing_date
                    if d.packaging_date and not merged_dates.packaging_date:
                        merged_dates.packaging_date = d.packaging_date
                    if d.expiry_date and not merged_dates.expiry_date:
                        merged_dates.expiry_date = d.expiry_date
                    if d.best_before and not merged_dates.best_before:
                        merged_dates.best_before = d.best_before
                    if d.raw_text and not merged_dates.raw_text:
                        merged_dates.raw_text = d.raw_text
                structured.dates = merged_dates
            elif isinstance(val, DateDetails):
                structured.dates = val
            else:
                norm_d = normalize_date(val)
                structured.dates.manufacturing_date = norm_d
                structured.dates.raw_text = raw_text

        elif field == "manufacturer":
            mfg_objs = [c.extracted_value for c in cluster if isinstance(c.extracted_value, ManufacturerDetails)]
            if mfg_objs:
                merged_mfg = ManufacturerDetails()
                for mo in mfg_objs:
                    if mo.name and not merged_mfg.name:
                        merged_mfg.name = mo.name
                    if mo.address and not merged_mfg.address:
                        merged_mfg.address = mo.address
                    if mo.pincode and not merged_mfg.pincode:
                        merged_mfg.pincode = mo.pincode
                    if mo.entity_type and not merged_mfg.entity_type:
                        merged_mfg.entity_type = mo.entity_type
                    if mo.raw_text and not merged_mfg.raw_text:
                        merged_mfg.raw_text = mo.raw_text
                structured.manufacturer = merged_mfg
            elif isinstance(val, ManufacturerDetails):
                structured.manufacturer = val
            else:
                structured.manufacturer.name = str(val)
                structured.manufacturer.raw_text = raw_text

        elif field == "consumer_care":
            care_objs = [c.extracted_value for c in cluster if isinstance(c.extracted_value, ConsumerCareDetails)]
            if care_objs:
                merged_care = ConsumerCareDetails()
                for co in care_objs:
                    if co.phone and not merged_care.phone:
                        merged_care.phone = co.phone
                    if co.email and not merged_care.email:
                        merged_care.email = co.email
                    if co.raw_text and not merged_care.raw_text:
                        merged_care.raw_text = co.raw_text
                structured.consumer_care = merged_care
            elif isinstance(val, ConsumerCareDetails):
                structured.consumer_care = val
            else:
                care_str = str(val)
                if "@" in care_str:
                    structured.consumer_care.email = care_str
                else:
                    structured.consumer_care.phone = care_str
                structured.consumer_care.raw_text = raw_text

        elif field == "product_name":
            structured.product_name = str(val)

        elif field == "common_or_generic_name":
            structured.common_or_generic_name = str(val)

        elif field == "country_of_origin":
            structured.country_of_origin = str(val)

    @classmethod
    def extract_candidates_from_structured_data(
        cls,
        image_id: int,
        image_role: str,
        sequence: int,
        data: StructuredProductData,
        ocr_result: Optional[OCRResult] = None
    ) -> List[EvidenceCandidate]:
        """Extracts field-level EvidenceCandidate records from a single view's StructuredProductData."""
        def _get_metadata(text_val: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
            if not ocr_result:
                if text_val:
                    res = ScriptDetector.analyze(str(text_val))
                    script = res.script if res.script != "UNKNOWN" else None
                    return None, script
                return None, None

            # 1. Search in OCR blocks for a matching text fragment
            if text_val:
                q = str(text_val).strip().lower()
                if q:
                    for b in ocr_result.blocks:
                        b_text = b.text.strip().lower()
                        if q in b_text or b_text in q:
                            return b.confidence, b.detected_script

            # 2. Fallback to image-level metadata
            conf = ocr_result.average_confidence if ocr_result.average_confidence > 0 else None
            dominant_script = None
            if ocr_result.blocks:
                scripts = [b.detected_script for b in ocr_result.blocks if b.detected_script and b.detected_script != "UNKNOWN"]
                if scripts:
                    dominant_script = max(set(scripts), key=scripts.count)
            if text_val:
                res = ScriptDetector.analyze(str(text_val))
                script = res.script if res.script != "UNKNOWN" else dominant_script
            else:
                script = dominant_script
            return conf, script

        candidates = []
        if data.product_name:
            c_conf, c_script = _get_metadata(data.product_name)
            candidates.append(EvidenceCandidate(
                field_name="product_name",
                extracted_value=data.product_name,
                source_image_id=image_id,
                source_role=image_role,
                source_sequence=sequence,
                source_text=data.product_name,
                confidence=c_conf,
                detected_script=c_script
            ))
        if data.common_or_generic_name:
            c_conf, c_script = _get_metadata(data.common_or_generic_name)
            candidates.append(EvidenceCandidate(
                field_name="common_or_generic_name",
                extracted_value=data.common_or_generic_name,
                source_image_id=image_id,
                source_role=image_role,
                source_sequence=sequence,
                source_text=data.common_or_generic_name,
                confidence=c_conf,
                detected_script=c_script
            ))
        if data.mrp and (data.mrp.value is not None or data.mrp.raw_text):
            mrp_val = data.mrp.value if data.mrp.value is not None else data.mrp.raw_text
            snippet = data.mrp.raw_text or str(mrp_val)
            c_conf, c_script = _get_metadata(snippet)
            candidates.append(EvidenceCandidate(
                field_name="mrp",
                extracted_value=mrp_val,
                source_image_id=image_id,
                source_role=image_role,
                source_sequence=sequence,
                source_text=snippet,
                confidence=c_conf,
                detected_script=c_script
            ))
        if data.net_quantity and (data.net_quantity.value is not None or data.net_quantity.piece_count is not None or data.net_quantity.raw_text):
            qty_val = (
                f"{data.net_quantity.value} {data.net_quantity.unit}".strip()
                if data.net_quantity.value is not None
                else (f"{data.net_quantity.piece_count} pcs" if data.net_quantity.piece_count is not None else data.net_quantity.raw_text)
            )
            snippet = data.net_quantity.raw_text or str(qty_val)
            c_conf, c_script = _get_metadata(snippet)
            candidates.append(EvidenceCandidate(
                field_name="net_quantity",
                extracted_value=qty_val,
                source_image_id=image_id,
                source_role=image_role,
                source_sequence=sequence,
                source_text=snippet,
                confidence=c_conf,
                detected_script=c_script
            ))
        usp_val = None
        if data.unit_sale_price:
            usp_val = data.unit_sale_price.raw_text if isinstance(data.unit_sale_price, UnitSalePriceDetails) else str(data.unit_sale_price)
        elif data.mrp and data.mrp.unit_sale_price:
            usp_val = data.mrp.unit_sale_price
        if usp_val:
            c_conf, c_script = _get_metadata(usp_val)
            candidates.append(EvidenceCandidate(
                field_name="unit_sale_price",
                extracted_value=usp_val,
                source_image_id=image_id,
                source_role=image_role,
                source_sequence=sequence,
                source_text=usp_val,
                confidence=c_conf,
                detected_script=c_script
            ))
        if data.dates and (data.dates.manufacturing_date or data.dates.packaging_date or data.dates.best_before or data.dates.raw_text):
            d_val = data.dates.manufacturing_date or data.dates.packaging_date or data.dates.best_before or data.dates.raw_text
            snippet = data.dates.raw_text or str(d_val)
            c_conf, c_script = _get_metadata(snippet)
            candidates.append(EvidenceCandidate(
                field_name="dates",
                extracted_value=data.dates if (data.dates.manufacturing_date or data.dates.packaging_date or data.dates.best_before) else d_val,
                source_image_id=image_id,
                source_role=image_role,
                source_sequence=sequence,
                source_text=snippet,
                confidence=c_conf,
                detected_script=c_script
            ))
        if data.manufacturer and (data.manufacturer.name or data.manufacturer.address or data.manufacturer.raw_text):
            mfg_text = data.manufacturer.raw_text or data.manufacturer.name or data.manufacturer.address
            c_conf, c_script = _get_metadata(mfg_text)
            candidates.append(EvidenceCandidate(
                field_name="manufacturer",
                extracted_value=data.manufacturer if (data.manufacturer.name or data.manufacturer.address) else mfg_text,
                source_image_id=image_id,
                source_role=image_role,
                source_sequence=sequence,
                source_text=mfg_text,
                confidence=c_conf,
                detected_script=c_script
            ))
        if data.consumer_care and (data.consumer_care.phone or data.consumer_care.email or data.consumer_care.raw_text):
            care_text = data.consumer_care.raw_text or data.consumer_care.phone or data.consumer_care.email
            c_conf, c_script = _get_metadata(care_text)
            candidates.append(EvidenceCandidate(
                field_name="consumer_care",
                extracted_value=data.consumer_care if (data.consumer_care.phone or data.consumer_care.email) else care_text,
                source_image_id=image_id,
                source_role=image_role,
                source_sequence=sequence,
                source_text=care_text,
                confidence=c_conf,
                detected_script=c_script
            ))
        if data.country_of_origin:
            c_conf, c_script = _get_metadata(data.country_of_origin)
            candidates.append(EvidenceCandidate(
                field_name="country_of_origin",
                extracted_value=data.country_of_origin,
                source_image_id=image_id,
                source_role=image_role,
                source_sequence=sequence,
                source_text=data.country_of_origin,
                confidence=c_conf,
                detected_script=c_script
            ))
        if data.batch_number:
            c_conf, c_script = _get_metadata(data.batch_number)
            candidates.append(EvidenceCandidate(
                field_name="batch_number",
                extracted_value=data.batch_number,
                source_image_id=image_id,
                source_role=image_role,
                source_sequence=sequence,
                source_text=data.batch_number,
                confidence=c_conf,
                detected_script=c_script
            ))
        return candidates

    @classmethod
    def fuse_images(cls, images_data: List[Dict[str, Any]]) -> EvidenceFusionResult:
        """Extracts and fuses declarations across multiple image data payloads."""
        candidates: List[EvidenceCandidate] = []
        for item in images_data:
            image_id = item["image_id"]
            image_role = item["image_role"]
            sequence = item.get("sequence", 1)
            ocr_res = item.get("ocr_result")
            if "structured_data" in item and item["structured_data"]:
                cands = cls.extract_candidates_from_structured_data(
                    image_id=image_id,
                    image_role=image_role,
                    sequence=sequence,
                    data=item["structured_data"],
                    ocr_result=ocr_res
                )
                candidates.extend(cands)
        return cls.fuse(candidates)
