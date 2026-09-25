import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR
from app.db.models import Inspection, InspectionImage
from app.ocr.preprocessor import ImagePreprocessor
from app.ocr.ocr_service import OCRService
from app.extractor.gemini_parser import StructuredDataExtractor
from app.rules.engine import rule_engine
from app.rules.models import ComplianceReport, ComplianceStatus
from app.schemas.product import StructuredProductData
from app.schemas.inspection import (
    ProcessedImageSummary,
    InspectionOCRSummary,
    InspectionProcessResponse
)
from app.inspection.aggregator import InspectionOCRAggregator
from app.inspection.fusion import EvidenceFusionEngine, EvidenceCandidate
from app.ocr.parser import detect_statutory_physical_signals, normalize_market_channel

logger = logging.getLogger(__name__)


def normalize_country_name(name: Optional[str]) -> Optional[str]:
    """Normalize country string for comparison without aggressive assumptions."""
    if not name or not isinstance(name, str):
        return None
    cleaned = name.strip().lower()
    return cleaned if cleaned else None


INDIA_ALIASES = {
    "india",
    "ind",
    "in",
    "bharat",
    "republic of india"
}


def is_india_country(name: Optional[str]) -> bool:
    norm = normalize_country_name(name)
    return norm in INDIA_ALIASES if norm else False


def is_foreign_country(name: Optional[str]) -> bool:
    norm = normalize_country_name(name)
    if not norm:
        return False
    return norm not in INDIA_ALIASES


def build_context_provenance(
    inspection: Inspection,
    structured_data: Optional[StructuredProductData] = None,
    ocr_text: Optional[str] = None,
    market_channel: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constructs a structured context provenance object distinguishing explicit user inputs,
    extracted package declarations, deterministic derived facts, and conflicts.
    Preserves missing values as None rather than fabricating defaults.
    Incorporates market channel corroboration, statutory physical markings, and Chapter II applicability scoping.
    """
    # Determine raw claimed channel: explicit argument takes precedence over model attribute
    raw_channel = market_channel if market_channel is not None else getattr(inspection, "market_channel", None)
    normalized_channel = normalize_market_channel(raw_channel)

    # 1. Explicit inputs from inspection record
    explicit = {
        "is_imported": inspection.is_imported,
        "commodity_type": inspection.commodity_type,
        "country_of_manufacture": inspection.country_of_manufacture,
        "country_of_sale": inspection.country_of_sale,
        "claimed_channel": raw_channel
    }

    # 2. Extracted evidence from structured package data and OCR physical signals
    mfg_entity_type = None
    extracted_origin = None
    if structured_data:
        extracted_origin = structured_data.country_of_origin
        if structured_data.manufacturer:
            mfg_entity_type = structured_data.manufacturer.entity_type

    # Scan OCR text or structured snippets for statutory physical markings
    text_to_scan = ocr_text or ""
    if not text_to_scan and structured_data:
        snippets = []
        if structured_data.other_declarations:
            snippets.extend(structured_data.other_declarations)
        if structured_data.mrp and structured_data.mrp.raw_text:
            snippets.append(structured_data.mrp.raw_text)
        if structured_data.net_quantity and structured_data.net_quantity.raw_text:
            snippets.append(structured_data.net_quantity.raw_text)
        if structured_data.manufacturer and structured_data.manufacturer.raw_text:
            snippets.append(structured_data.manufacturer.raw_text)
        if structured_data.consumer_care and structured_data.consumer_care.raw_text:
            snippets.append(structured_data.consumer_care.raw_text)
        if structured_data.dates and structured_data.dates.raw_text:
            snippets.append(structured_data.dates.raw_text)
        text_to_scan = " ".join(snippets)

    physical_signals = detect_statutory_physical_signals(text_to_scan)

    extracted = {
        "country_of_origin": extracted_origin,
        "entity_type": mfg_entity_type,
        "physical_signals": physical_signals
    }

    # 3. Derived determinations
    derived = {}
    if inspection.country_of_manufacture:
        derived["manufacture_is_foreign"] = is_foreign_country(inspection.country_of_manufacture)
        derived["manufacture_is_india"] = is_india_country(inspection.country_of_manufacture)

    if extracted_origin:
        derived["origin_is_foreign"] = is_foreign_country(extracted_origin)
        derived["origin_is_india"] = is_india_country(extracted_origin)

    derived["normalized_channel"] = normalized_channel

    # 4. Context conflicts & statutory determination
    conflicts = []

    # Import vs Manufacture conflicts
    if inspection.is_imported is False and inspection.country_of_manufacture:
        if is_foreign_country(inspection.country_of_manufacture):
            conflicts.append({
                "field": "is_imported",
                "conflict_type": "IMPORT_STATUS_CONTRADICTION",
                "message": (
                    f"Explicit is_imported is False, but country of manufacture is "
                    f"'{inspection.country_of_manufacture}' (foreign)."
                ),
                "explicit_value": False,
                "competing_value": inspection.country_of_manufacture
            })

    if inspection.is_imported is True and inspection.country_of_manufacture:
        if is_india_country(inspection.country_of_manufacture):
            conflicts.append({
                "field": "is_imported",
                "conflict_type": "IMPORT_STATUS_CONTRADICTION",
                "message": (
                    f"Explicit is_imported is True, but country of manufacture is "
                    f"'{inspection.country_of_manufacture}' (India)."
                ),
                "explicit_value": True,
                "competing_value": inspection.country_of_manufacture
            })

    # Statutory physical signal flags
    not_for_retail = physical_signals["not_for_retail_sale_detected"]
    for_ind_only = physical_signals["for_industrial_use_only_detected"]
    for_export_only = physical_signals["for_export_only_detected"]

    # Market context evaluation
    commercial_context_verified = False
    customs_export_transit_verified = False
    digital_listing_verified = False

    chapter_ii_applicable = True
    applicable_chapter = "CHAPTER_II"
    statutory_basis = "Rule 3 (Default Domestic Retail)"
    determination_status = "DETERMINED"

    if normalized_channel == "INSTITUTIONAL":
        if not_for_retail:
            chapter_ii_applicable = False
            applicable_chapter = "CHAPTER_II"
            statutory_basis = "Rule 3(b) read with Rule 2(bc)"
            determination_status = "NOT_APPLICABLE"
            commercial_context_verified = False
        else:
            chapter_ii_applicable = True
            applicable_chapter = "CHAPTER_II"
            statutory_basis = "Rule 3 (Chapter II enforced: mandatory non-retail declaration missing)"
            determination_status = "ENFORCED"
            conflicts.append({
                "field": "market_channel",
                "conflict_type": "UNCORROBORATED_INSTITUTIONAL_CLAIM",
                "message": (
                    "Claimed channel is INSTITUTIONAL, but physical packaging lacks mandatory statutory "
                    "declaration 'not for retail sale' required under Rule 2(bc). Chapter II retail scrutiny enforced."
                ),
                "explicit_value": raw_channel,
                "competing_value": None,
                "severity": "WARNING"
            })

    elif normalized_channel == "INDUSTRIAL":
        if not_for_retail or for_ind_only:
            chapter_ii_applicable = False
            applicable_chapter = "CHAPTER_II"
            statutory_basis = "Rule 3(b) read with Rule 2(bb)"
            determination_status = "NOT_APPLICABLE"
            commercial_context_verified = False
        else:
            chapter_ii_applicable = True
            applicable_chapter = "CHAPTER_II"
            statutory_basis = "Rule 3 (Chapter II enforced: mandatory non-retail declaration missing)"
            determination_status = "ENFORCED"
            conflicts.append({
                "field": "market_channel",
                "conflict_type": "UNCORROBORATED_INDUSTRIAL_CLAIM",
                "message": (
                    "Claimed channel is INDUSTRIAL, but physical packaging lacks mandatory statutory "
                    "declaration 'not for retail sale' (Rule 2(bb)) or recognized industrial marking 'for industrial use only'. "
                    "Chapter II retail scrutiny enforced."
                ),
                "explicit_value": raw_channel,
                "competing_value": None,
                "severity": "WARNING"
            })

    elif normalized_channel == "ECOMMERCE":
        chapter_ii_applicable = True
        applicable_chapter = "CHAPTER_II"
        statutory_basis = "Rule 3 & Rule 6(1) (E-commerce physical packages require full Chapter II compliance)"
        determination_status = "DETERMINED"
        digital_listing_verified = False

    elif normalized_channel == "EXPORT":
        customs_export_transit_verified = False
        sale_is_domestic = is_india_country(inspection.country_of_sale) if inspection.country_of_sale else False
        mrp_present = bool(structured_data and structured_data.mrp and structured_data.mrp.value is not None)

        if sale_is_domestic or (mrp_present and structured_data and getattr(structured_data.mrp, "currency", "INR") == "INR"):
            chapter_ii_applicable = True
            applicable_chapter = "CHAPTER_IV_RULE_25"
            statutory_basis = "Rule 25 (Chapter IV: Potential domestic retail diversion / contradictory domestic context)"
            determination_status = "REQUIRES_REVIEW"
            conflicts.append({
                "field": "market_channel",
                "conflict_type": "EXPORT_DOMESTIC_TARGET_CONFLICT",
                "message": (
                    "Export channel claimed, but package is designated for domestic sale in India or bears "
                    "domestic retail pricing markers. Requires human regulatory review under Chapter IV, Rule 25."
                ),
                "explicit_value": raw_channel,
                "competing_value": inspection.country_of_sale or "Domestic markers",
                "severity": "WARNING"
            })
        else:
            chapter_ii_applicable = True
            applicable_chapter = "CHAPTER_IV"
            if for_export_only:
                statutory_basis = "Rule 25 (Chapter IV: Physical export marking detected, customs transit unverified)"
                determination_status = "REQUIRES_REVIEW"
            else:
                statutory_basis = "Rule 25 & Rule 3 (Export claim uncorroborated; Chapter II baseline scrutiny maintained)"
                determination_status = "REQUIRES_REVIEW"
                conflicts.append({
                    "field": "market_channel",
                    "conflict_type": "UNCORROBORATED_EXPORT_CLAIM",
                    "message": (
                        "Export channel claimed, but package lacks physical 'for export only' declaration. "
                        "Chapter II baseline scrutiny maintained."
                    ),
                    "explicit_value": raw_channel,
                    "competing_value": None,
                    "severity": "WARNING"
                })

    elif normalized_channel == "UNKNOWN":
        chapter_ii_applicable = True
        applicable_chapter = "CHAPTER_II"
        statutory_basis = "Special market-context exemption not established."
        determination_status = "DETERMINED"

    elif normalized_channel == "RETAIL":
        chapter_ii_applicable = True
        applicable_chapter = "CHAPTER_II"
        statutory_basis = "Rule 3 (Standard Domestic Retail)"
        determination_status = "DETERMINED"

    derived["chapter_ii_applicable"] = chapter_ii_applicable

    market_context = {
        "claimed_channel": raw_channel,
        "normalized_channel": normalized_channel
    }

    statutory_determination = {
        "applicable_chapter": applicable_chapter,
        "chapter_ii_applicable": chapter_ii_applicable,
        "statutory_basis": statutory_basis,
        "determination_status": determination_status
    }

    diagnostics = {
        "commercial_context_verified": commercial_context_verified,
        "customs_export_transit_verified": customs_export_transit_verified,
        "digital_listing_verified": digital_listing_verified,
        "anomalies": conflicts,
        "conflicts": conflicts
    }

    return {
        "explicit": explicit,
        "extracted": extracted,
        "derived": derived,
        "conflicts": conflicts,
        "market_context": market_context,
        "physical_signals": physical_signals,
        "statutory_determination": statutory_determination,
        "diagnostics": diagnostics
    }


class InspectionProcessor:
    """
    Orchestrates the multi-image inspection processing lifecycle:
    1. Loads parent Inspection and all associated InspectionImage records.
    2. Sequentially executes OpenCV preprocessing and RapidOCR on each image.
    3. Handles partial image failures gracefully without halting remaining views.
    4. Aggregates multi-image OCR evidence with origin provenance.
    5. Runs structured data extraction once on the combined text representation.
    6. Runs the deterministic Legal Metrology rule engine once on the unified declarations.
    7. Persists the unified state and returns an auditable inspection result.
    """

    @classmethod
    async def process_inspection(
        cls,
        db: Session,
        inspection_id: str,
        market_channel: Optional[str] = None
    ) -> InspectionProcessResponse:
        # Step 1: Load Inspection record
        inspection = db.query(Inspection).filter(Inspection.inspection_id == inspection_id).first()
        if not inspection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inspection '{inspection_id}' not found."
            )

        # Step 2: Load associated images ordered by sequence
        images = db.query(InspectionImage).filter(
            InspectionImage.inspection_id == inspection_id
        ).order_by(InspectionImage.sequence.asc(), InspectionImage.id.asc()).all()

        if not images or len(images) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Inspection '{inspection_id}' has no attached packaging images. Attach at least one image before processing."
            )

        # Step 3: Transition lifecycle status to PROCESSING
        inspection.status = "PROCESSING"
        db.commit()

        processed_images_summary: List[ProcessedImageSummary] = []
        successful_images_data: List[Dict[str, Any]] = []
        warnings: List[str] = []

        # Step 4: Process every image independently through Preprocessing + RapidOCR
        for img_record in images:
            img_record.processing_status = "PROCESSING"
            db.commit()

            # 4a. Validate file path existence
            if not img_record.image_path:
                warning_msg = f"Image ID {img_record.id} ({img_record.image_role}) has no file path recorded."
                warnings.append(warning_msg)
                img_record.processing_status = "FAILED"
                img_record.processing_error = warning_msg
                db.commit()
                processed_images_summary.append(
                    ProcessedImageSummary(
                        image_id=img_record.id,
                        image_role=img_record.image_role,
                        sequence=img_record.sequence,
                        status="FAILED",
                        error=warning_msg
                    )
                )
                continue

            disk_path = BACKEND_DIR / img_record.image_path
            if not disk_path.is_file():
                warning_msg = f"Image ID {img_record.id} ({img_record.image_role}) file not found on disk: {img_record.image_path}"
                warnings.append(warning_msg)
                img_record.processing_status = "FAILED"
                img_record.processing_error = warning_msg
                db.commit()
                processed_images_summary.append(
                    ProcessedImageSummary(
                        image_id=img_record.id,
                        image_role=img_record.image_role,
                        sequence=img_record.sequence,
                        status="FAILED",
                        error=warning_msg
                    )
                )
                continue

            # 4b. Read image contents and decode with OpenCV
            try:
                with open(disk_path, "rb") as f:
                    image_bytes = f.read()
                cv_img = ImagePreprocessor.decode_image_bytes(image_bytes)
            except Exception as e:
                warning_msg = f"Image ID {img_record.id} ({img_record.image_role}) image validation/decode failed: {str(e)}"
                warnings.append(warning_msg)
                img_record.processing_status = "FAILED"
                img_record.processing_error = warning_msg
                db.commit()
                processed_images_summary.append(
                    ProcessedImageSummary(
                        image_id=img_record.id,
                        image_role=img_record.image_role,
                        sequence=img_record.sequence,
                        status="FAILED",
                        error=warning_msg
                    )
                )
                continue

            # 4c. Contrast enhancement and resize for optimal OCR
            try:
                resized_img, _ = ImagePreprocessor.resize_for_ocr(cv_img)
                enhanced_img, _ = ImagePreprocessor.enhance_contrast(resized_img)
            except Exception as e:
                logger.warning(f"Enhancement fallback for image {img_record.id}: {e}")
                enhanced_img = cv_img

            # 4d. Run OCR inference via RapidOCR singleton
            try:
                ocr_result = OCRService.extract_from_image(enhanced_img)
                img_record.ocr_result_json = ocr_result.model_dump_json()
                img_record.processing_status = "COMPLETED"
                img_record.processing_error = None
                db.commit()

                successful_images_data.append({
                    "image_id": img_record.id,
                    "image_role": img_record.image_role,
                    "sequence": img_record.sequence,
                    "ocr_result": ocr_result
                })
                processed_images_summary.append(
                    ProcessedImageSummary(
                        image_id=img_record.id,
                        image_role=img_record.image_role,
                        sequence=img_record.sequence,
                        status="COMPLETED",
                        ocr_confidence=ocr_result.average_confidence,
                        block_count=ocr_result.block_count
                    )
                )
            except Exception as e:
                warning_msg = f"Image ID {img_record.id} ({img_record.image_role}) OCR failed: {str(e)}"
                warnings.append(warning_msg)
                img_record.processing_status = "FAILED"
                img_record.processing_error = warning_msg
                db.commit()
                processed_images_summary.append(
                    ProcessedImageSummary(
                        image_id=img_record.id,
                        image_role=img_record.image_role,
                        sequence=img_record.sequence,
                        status="FAILED",
                        error=warning_msg
                    )
                )

        # Step 5: Evaluate all-images failure condition
        if len(successful_images_data) == 0:
            inspection.status = "FAILED"
            inspection.compliance_status = "INSUFFICIENT_DATA"
            fail_structured = StructuredProductData(
                extraction_method="failed_all_images",
                extraction_confidence=0.0
            )
            context_prov = build_context_provenance(
                inspection,
                fail_structured,
                ocr_text="",
                market_channel=market_channel
            )
            context = {
                "is_imported": inspection.is_imported,
                "commodity_type": inspection.commodity_type or "",
                "country_of_manufacture": inspection.country_of_manufacture,
                "country_of_sale": inspection.country_of_sale,
                "market_channel": context_prov["market_context"]["normalized_channel"],
                "chapter_ii_applicable": context_prov["statutory_determination"]["chapter_ii_applicable"],
                "context_provenance": context_prov
            }
            fail_report = rule_engine.evaluate_compliance(fail_structured, context=context)
            empty_ocr_summary = InspectionOCRSummary(
                combined_text="",
                total_blocks=0,
                average_confidence=0.0,
                blocks=[]
            )

            inspection.structured_data_json = fail_structured.model_dump_json()
            inspection.compliance_report_json = fail_report.model_dump_json()
            inspection.ocr_summary_json = empty_ocr_summary.model_dump_json()
            inspection.provenance_json = "{}"
            db.commit()

            return InspectionProcessResponse(
                inspection_id=inspection.inspection_id,
                status="FAILED",
                compliance_status="INSUFFICIENT_DATA",
                images_total=len(images),
                images_processed=0,
                images=processed_images_summary,
                ocr_summary=empty_ocr_summary,
                structured_data=fail_structured,
                compliance_report=fail_report,
                provenance={},
                context_provenance=context_prov,
                warnings=warnings
            )

        # Step 6: Combine OCR evidence across all successful images
        ocr_summary = InspectionOCRAggregator.aggregate_ocr(successful_images_data)

        # Step 7: Extract field-level evidence candidates across each image view
        all_candidates: List[EvidenceCandidate] = []
        for item in successful_images_data:
            img_ocr = item["ocr_result"]
            try:
                image_structured = await StructuredDataExtractor.extract(img_ocr.full_text)
                candidates = EvidenceFusionEngine.extract_candidates_from_structured_data(
                    image_id=item["image_id"],
                    image_role=item["image_role"],
                    sequence=item["sequence"],
                    data=image_structured,
                    ocr_result=img_ocr
                )
                all_candidates.extend(candidates)
            except Exception as e:
                logger.warning(f"Structured extraction error for image {item['image_id']}: {e}")
                warnings.append(f"Image {item['image_id']} extraction warning: {str(e)}")

        # Step 8: Reconcile evidence across views using EvidenceFusionEngine
        fusion_result = EvidenceFusionEngine.fuse(all_candidates)
        structured_data = fusion_result.structured_data

        # Use Inspection-level product name if structured extraction did not detect one
        if inspection.product_name and not structured_data.product_name:
            structured_data.product_name = inspection.product_name

        # Step 9: Run deterministic Legal Metrology rule engine on consolidated product declarations
        context_prov = build_context_provenance(
            inspection,
            structured_data,
            ocr_text=ocr_summary.combined_text,
            market_channel=market_channel
        )
        context = {
            "is_imported": inspection.is_imported,
            "commodity_type": inspection.commodity_type or "",
            "country_of_manufacture": inspection.country_of_manufacture,
            "country_of_sale": inspection.country_of_sale,
            "market_channel": context_prov["market_context"]["normalized_channel"],
            "chapter_ii_applicable": context_prov["statutory_determination"]["chapter_ii_applicable"],
            "context_provenance": context_prov
        }
        compliance_report = rule_engine.evaluate_compliance(structured_data, context=context)

        # Step 10: Persist complete inspection results into database
        provenance = fusion_result.provenance
        inspection.status = "COMPLETED"
        inspection.compliance_status = compliance_report.compliance_status.value
        inspection.ocr_summary_json = ocr_summary.model_dump_json()
        inspection.structured_data_json = structured_data.model_dump_json()
        inspection.compliance_report_json = compliance_report.model_dump_json()
        inspection.provenance_json = json.dumps({
            k: v.model_dump() if v else None for k, v in provenance.items()
        })
        db.commit()

        return InspectionProcessResponse(
            inspection_id=inspection.inspection_id,
            status="COMPLETED",
            compliance_status=compliance_report.compliance_status.value,
            images_total=len(images),
            images_processed=len(successful_images_data),
            images=processed_images_summary,
            ocr_summary=ocr_summary,
            structured_data=structured_data,
            compliance_report=compliance_report,
            provenance=provenance,
            context_provenance=context_prov,
            conflicts=fusion_result.conflicts,
            is_conflicted=fusion_result.is_conflicted,
            warnings=warnings
        )
