import logging
from typing import List, Dict, Any, Optional

from app.schemas.ocr import OCRResult
from app.schemas.product import StructuredProductData
from app.schemas.inspection import (
    InspectionOCRBlock,
    InspectionOCRSummary,
    FieldProvenance
)

logger = logging.getLogger(__name__)


class InspectionOCRAggregator:
    """
    Combines independent OCR extractions from multiple package views (front, back, etc.)
    into a unified OCR evidence model with full source-image provenance.
    """

    @classmethod
    def aggregate_ocr(cls, images_data: List[Dict[str, Any]]) -> InspectionOCRSummary:
        """
        Merges OCR text blocks from all successfully processed images, preserving
        image_id, image_role, and sequence for every detected block.

        Generates a normalized, role-delimited text representation suitable for the
        existing structured extraction engine.
        """
        # Sort images deterministically by sequence and then image_id
        sorted_images = sorted(images_data, key=lambda x: (x.get("sequence", 1), x.get("image_id", 0)))

        all_blocks: List[InspectionOCRBlock] = []
        confidences: List[float] = []
        sections: List[str] = []

        for item in sorted_images:
            image_id = item["image_id"]
            image_role = item["image_role"]
            sequence = item["sequence"]
            ocr_res: OCRResult = item["ocr_result"]

            # Tag each block with image identity and coordinates
            for b in ocr_res.blocks:
                all_blocks.append(
                    InspectionOCRBlock(
                        image_id=image_id,
                        image_role=image_role,
                        sequence=sequence,
                        text=b.text,
                        confidence=b.confidence,
                        polygon=b.polygon,
                        box_2d=b.box_2d,
                        detected_script=getattr(b, "detected_script", "LATIN"),
                        script_confidence=getattr(b, "script_confidence", 1.0)
                    )
                )
                confidences.append(b.confidence)

            # Generate role-delimited text block
            role_header = f"--- {image_role.upper()} ---"
            clean_text = (ocr_res.full_text or "").strip()
            if clean_text:
                sections.append(f"{role_header}\n{clean_text}")
            else:
                sections.append(f"{role_header}\n[No text detected]")

        combined_text = "\n\n".join(sections)
        avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

        return InspectionOCRSummary(
            combined_text=combined_text,
            total_blocks=len(all_blocks),
            average_confidence=avg_confidence,
            blocks=all_blocks
        )

    @classmethod
    def build_provenance(
        cls,
        structured: StructuredProductData,
        images_data: List[Dict[str, Any]]
    ) -> Dict[str, Optional[FieldProvenance]]:
        """
        Maps each high-level mandatory declaration back to its originating image and text.
        Never loses provenance of detected declarations.
        """
        sorted_images = sorted(images_data, key=lambda x: (x.get("sequence", 1), x.get("image_id", 0)))
        provenance: Dict[str, Optional[FieldProvenance]] = {}

        def _resolve_source(val: Any, candidate_phrases: List[Optional[str]]) -> Optional[FieldProvenance]:
            clean_candidates = [
                str(c).strip() for c in candidate_phrases if c is not None and len(str(c).strip()) >= 2
            ]
            if not clean_candidates:
                return None

            # 1. Search in granular OCR blocks
            for cand in clean_candidates:
                cand_lower = cand.lower()
                for item in sorted_images:
                    ocr_res: OCRResult = item["ocr_result"]
                    for b in ocr_res.blocks:
                        if cand_lower in b.text.lower():
                            return FieldProvenance(
                                value=val,
                                source_image_id=item["image_id"],
                                source_role=item["image_role"],
                                source_sequence=item["sequence"],
                                source_text=b.text
                            )

            # 2. Search line-by-line in full_text
            for cand in clean_candidates:
                cand_lower = cand.lower()
                for item in sorted_images:
                    ocr_res: OCRResult = item["ocr_result"]
                    for line in (ocr_res.full_text or "").splitlines():
                        if cand_lower in line.lower():
                            return FieldProvenance(
                                value=val,
                                source_image_id=item["image_id"],
                                source_role=item["image_role"],
                                source_sequence=item["sequence"],
                                source_text=line.strip()
                            )

            return None

        # 1. MRP declaration
        mrp_val = structured.mrp.value if structured.mrp else None
        mrp_candidates = [
            structured.mrp.raw_text if structured.mrp else None,
            str(mrp_val) if mrp_val is not None else None,
            f"₹{mrp_val}" if mrp_val is not None else None,
            f"Rs {mrp_val}" if mrp_val is not None else None,
            "MRP",
            "M.R.P",
            "अधिकतम खुदरा मूल्य",
            "अधिकतमखुदरामूल्य",
            "खुदरा मूल्य",
            "मूल्य"
        ]
        provenance["mrp"] = _resolve_source(mrp_val, mrp_candidates) if mrp_val is not None else None

        # 2. Net Quantity declaration
        net_qty_val = (
            f"{structured.net_quantity.value} {structured.net_quantity.unit}".strip()
            if structured.net_quantity and structured.net_quantity.value is not None
            else (structured.net_quantity.raw_text if structured.net_quantity else None)
        )
        net_qty_candidates = [
            structured.net_quantity.raw_text if structured.net_quantity else None,
            str(structured.net_quantity.value) if (structured.net_quantity and structured.net_quantity.value) else None,
            "Net Qty",
            "Net Weight",
            "Net Quantity",
            "Net Volume",
            "शुद्ध मात्रा",
            "शुद्धमात्रा",
            "मात्रा"
        ]
        provenance["net_quantity"] = _resolve_source(net_qty_val, net_qty_candidates) if net_qty_val else None

        # 3. Manufacturer / Packer details
        mfg_val = structured.manufacturer.name if structured.manufacturer else None
        mfg_candidates = [
            structured.manufacturer.name if structured.manufacturer else None,
            structured.manufacturer.address if structured.manufacturer else None,
            structured.manufacturer.raw_text if structured.manufacturer else None,
            "Manufactured by",
            "Mfg by",
            "Packed by",
            "Marketed by",
            "निर्माता",
            "पैककर्ता",
            "उत्पादक",
            "आयातकर्ता"
        ]
        provenance["manufacturer"] = _resolve_source(mfg_val, mfg_candidates) if mfg_val else None

        # 4. Consumer Care details
        care_val = (
            structured.consumer_care.phone or structured.consumer_care.email
            if structured.consumer_care else None
        )
        care_candidates = [
            structured.consumer_care.phone if structured.consumer_care else None,
            structured.consumer_care.email if structured.consumer_care else None,
            structured.consumer_care.raw_text if structured.consumer_care else None,
            "Customer Care",
            "Consumer Care",
            "Toll Free",
            "Helpline",
            "उपभोक्ता देखभाल",
            "उपभोक्तादेखभाल",
            "ग्राहक सेवा",
            "हेल्पलाइन"
        ]
        provenance["consumer_care"] = _resolve_source(care_val, care_candidates) if care_val else None

        # 5. Date declarations (Manufacturing, Packing, Best Before)
        date_val = (
            structured.dates.manufacturing_date
            or structured.dates.packaging_date
            or structured.dates.best_before
            if structured.dates else None
        )
        date_candidates = [
            structured.dates.manufacturing_date if structured.dates else None,
            structured.dates.packaging_date if structured.dates else None,
            structured.dates.expiry_date if structured.dates else None,
            structured.dates.best_before if structured.dates else None,
            structured.dates.raw_text if structured.dates else None,
            "Mfg Date",
            "Date of Mfg",
            "Pkd Date",
            "Best Before",
            "निर्माण तिथि",
            "निर्माणतिथि",
            "पैकिंग तिथि",
            "पैकिंगतिथि"
        ]
        provenance["dates"] = _resolve_source(date_val, date_candidates) if date_val else None

        # 6. Product Name
        name_val = structured.product_name or structured.common_or_generic_name
        name_candidates = [
            structured.product_name,
            structured.common_or_generic_name
        ]
        provenance["product_name"] = _resolve_source(name_val, name_candidates) if name_val else None

        # 7. Country of Origin
        coo_val = structured.country_of_origin
        coo_candidates = [
            structured.country_of_origin,
            "Country of Origin",
            "Made in",
            "Manufactured in",
            "मूल देश",
            "उत्पत्ति का देश",
            "भारत"
        ]
        provenance["country_of_origin"] = _resolve_source(coo_val, coo_candidates) if coo_val else None

        return provenance
