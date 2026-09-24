import json
import logging
from typing import List, Dict, Any
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

logger = logging.getLogger(__name__)


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
        inspection_id: str
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
            context = {
                "is_imported": inspection.is_imported,
                "commodity_type": inspection.commodity_type or ""
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
        context = {
            "is_imported": inspection.is_imported,
            "commodity_type": inspection.commodity_type or ""
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
            conflicts=fusion_result.conflicts,
            is_conflicted=fusion_result.is_conflicted,
            warnings=warnings
        )
