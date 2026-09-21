import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.upload import ImageDimensions
from app.schemas.ocr import OCRResult
from app.schemas.product import StructuredProductData
from app.rules.models import (
    ComplianceReport,
    ComplianceCheckRequest
)
from app.rules.engine import rule_engine
from app.ocr.preprocessor import ImagePreprocessor
from app.ocr.ocr_service import OCRService
from app.extractor.gemini_parser import StructuredDataExtractor
from app.db.session import get_db
from app.db import crud


router = APIRouter()

class FullInspectionResponse(BaseModel):
    success: bool = Field(True, description="Indicates if full inspection completed")
    file_id: str = Field(..., description="Unique scan session ID")
    image_dimensions: ImageDimensions = Field(..., description="Processed image dimensions")
    ocr_result: OCRResult = Field(..., description="Detected text fragments with bounding boxes")
    structured_data: StructuredProductData = Field(..., description="Structured product declarations")
    compliance_report: ComplianceReport = Field(..., description="Deterministic Legal Metrology compliance verdict")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 15 * 1024 * 1024

@router.post(
    "/compliance/check",
    response_model=ComplianceReport,
    status_code=status.HTTP_200_OK,
    tags=["Legal Metrology Compliance Engine"],
    summary="Evaluate structured product data against Legal Metrology Rules, 2011",
    description="Deterministic rule engine checking declarations against Rule 6(1)(a), 6(1)(b), 6(1)(c), 6(1)(d), 6(1)(e), 6(1)(n), 6(10), 6(11) and Rule 26 exemptions."
)
async def check_compliance(
    request: ComplianceCheckRequest,
    db: Session = Depends(get_db)
):
    context = {
        "is_imported": request.is_imported or False,
        "commodity_type": request.commodity_type or ""
    }

    # Case A: Structured product data provided directly
    if request.data is not None:
        report = rule_engine.evaluate_compliance(request.data, context=context)
        if request.file_id:
            try:
                crud.save_or_update_scan(
                    db=db,
                    file_id=request.file_id,
                    structured_data=request.data,
                    compliance_report=report
                )
            except Exception:
                pass
        return report

    # Case B: file_id provided
    if request.file_id:
        proc_path = settings.UPLOAD_DIR / "processed" / f"{request.file_id}_preprocessed.png"
        if not proc_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Preprocessed image for file_id '{request.file_id}' not found."
            )

        # 1. OCR
        try:
            ocr_res = OCRService.extract_from_image(proc_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"OCR execution failed: {e}")

        # 2. Structured Extraction
        structured = await StructuredDataExtractor.extract(ocr_res.full_text)

        # 3. Rule Evaluation
        report = rule_engine.evaluate_compliance(structured, context=context)

        # 4. Save to DB
        try:
            crud.save_or_update_scan(
                db=db,
                file_id=request.file_id,
                processed_image_path=str(proc_path),
                ocr_result=ocr_res,
                structured_data=structured,
                compliance_report=report
            )
        except Exception:
            pass

        return report

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Must provide either 'data' (StructuredProductData) or 'file_id'."
    )

@router.post(
    "/compliance/inspect-file",
    response_model=FullInspectionResponse,
    status_code=status.HTTP_200_OK,
    tags=["Legal Metrology Compliance Engine"],
    summary="End-to-End Inspection: Image Upload -> OCR -> AI Structuring -> Legal Compliance Report",
    description="Accepts a package photo, runs preprocessing, text extraction, structured entity parsing, and deterministic statutory rule evaluation."
)
async def inspect_package_file(
    file: UploadFile = File(...),
    is_imported: bool = Form(False),
    commodity_type: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    # 1. File Validation
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{file_ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="File is empty (0 bytes).")

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 15 MB limit.")

    # 2. OpenCV Preprocess
    file_id = str(uuid.uuid4())
    try:
        proc_result = ImagePreprocessor.process_and_save(
            image_bytes=contents,
            file_id=file_id,
            original_filename=file.filename or "package.jpg",
            upload_base_dir=settings.UPLOAD_DIR
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preprocessing failed: {e}")

    # 3. OCR Text Extraction
    proc_path = proc_result["processed_saved_path"]
    try:
        ocr_result = OCRService.extract_from_image(proc_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {e}")

    # 4. AI Structured Extraction
    structured = await StructuredDataExtractor.extract(ocr_result.full_text)

    # 5. Deterministic Rule Engine
    context = {
        "is_imported": is_imported,
        "commodity_type": commodity_type or ""
    }
    report = rule_engine.evaluate_compliance(structured, context=context)

    # 6. Save inspection record to SQLite database for audit log / scan history
    crud.save_or_update_scan(
        db=db,
        file_id=file_id,
        original_filename=file.filename,
        image_path=str(proc_result["original_saved_path"]),
        processed_image_path=str(proc_result["processed_saved_path"]),
        ocr_result=ocr_result,
        structured_data=structured,
        compliance_report=report
    )

    proc_dims = proc_result["processed_image"]["dimensions"]

    return FullInspectionResponse(
        success=True,
        file_id=file_id,
        image_dimensions=ImageDimensions(
            width=proc_dims["width"],
            height=proc_dims["height"],
            channels=proc_dims.get("channels", 3)
        ),
        ocr_result=ocr_result,
        structured_data=structured,
        compliance_report=report
    )
