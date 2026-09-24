import uuid
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.core.config import settings, BACKEND_DIR
from app.db.session import get_db
from app.db.models import Inspection, InspectionImage, VALID_IMAGE_ROLES
from app.schemas.inspection import (
    InspectionCreate,
    InspectionResponse,
    InspectionDetailResponse,
    InspectionImageResponse,
    InspectionDeleteResponse,
    InspectionImageDeleteResponse,
    InspectionProcessResponse
)
from app.ocr.preprocessor import ImagePreprocessor
from app.inspection.processor import InspectionProcessor

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/inspections",
    tags=["Product Inspections (Multi-Image Foundation)"]
)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB


@router.post(
    "",
    response_model=InspectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product inspection session"
)
@router.post(
    "/",
    response_model=InspectionResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def create_inspection(
    payload: Optional[InspectionCreate] = None,
    db: Session = Depends(get_db)
):
    """
    Creates a new product inspection record.
    Supports optional commodity metadata and notes.
    Does not trigger OCR or compliance processing.
    """
    data = payload.model_dump() if payload else {}
    inspection = Inspection(
        inspection_id=str(uuid.uuid4()),
        product_name=data.get("product_name"),
        country_of_manufacture=data.get("country_of_manufacture"),
        country_of_sale=data.get("country_of_sale"),
        is_imported=data.get("is_imported", False),
        commodity_type=data.get("commodity_type"),
        inspection_notes=data.get("inspection_notes"),
        status="PENDING"
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


@router.get(
    "/{inspection_id}",
    response_model=InspectionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve inspection metadata and attached images"
)
def get_inspection(
    inspection_id: str,
    db: Session = Depends(get_db)
):
    """
    Fetches full inspection metadata and all associated package images
    ordered by display sequence.
    """
    inspection = db.query(Inspection).filter(Inspection.inspection_id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found."
        )
    return inspection


@router.post(
    "/{inspection_id}/images",
    response_model=InspectionImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach an image to an existing inspection"
)
async def attach_inspection_image(
    inspection_id: str,
    file: UploadFile = File(...),
    image_role: str = Form(...),
    sequence: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Validates and stores a packaging image attached to an existing inspection session.
    Enforces format, size, decodability, and supported image roles.
    Does not trigger OCR or compliance processing.
    """
    # 1. Verify parent inspection exists
    inspection = db.query(Inspection).filter(Inspection.inspection_id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found."
        )

    # 2. Validate image_role
    if image_role not in VALID_IMAGE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image_role '{image_role}'. Must be one of: {', '.join(sorted(VALID_IMAGE_ROLES))}"
        )

    # 3. Validate file extension
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_ext}'. Allowed formats are: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 4. Validate MIME type
    if file.content_type and file.content_type.lower() not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type '{file.content_type}'. Must be one of: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
        )

    # 5. Read contents and check size
    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read uploaded file: {str(e)}"
        )

    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)."
        )

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE // (1024 * 1024)} MB."
        )

    # 6. Validate decodability with OpenCV
    try:
        _ = ImagePreprocessor.decode_image_bytes(contents)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image validation error: {str(e)}"
        )

    # 7. Determine sequence index
    if sequence is not None:
        assigned_sequence = sequence
    else:
        existing_sequences = [img.sequence for img in inspection.images]
        assigned_sequence = (max(existing_sequences) + 1) if existing_sequences else 1

    # 8. Save file to disk using standard upload conventions
    file_id = str(uuid.uuid4())
    clean_name = Path(file.filename or "upload.jpg").name.replace(" ", "_")
    saved_filename = f"{file_id}_{clean_name}"
    orig_dir = settings.UPLOAD_DIR / "original"
    orig_dir.mkdir(parents=True, exist_ok=True)
    target_path = orig_dir / saved_filename

    with open(target_path, "wb") as f:
        f.write(contents)

    relative_path = f"uploads/original/{saved_filename}"

    # 9. Create InspectionImage record
    image_record = InspectionImage(
        inspection_id=inspection.inspection_id,
        file_id=file_id,
        original_filename=file.filename or "unknown",
        image_path=relative_path,
        image_role=image_role,
        sequence=assigned_sequence,
        processing_status="PENDING"
    )
    db.add(image_record)
    db.commit()
    db.refresh(image_record)

    return image_record


@router.delete(
    "/{inspection_id}/images/{image_id}",
    response_model=InspectionImageDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an image from an inspection session"
)
def delete_inspection_image(
    inspection_id: str,
    image_id: int,
    db: Session = Depends(get_db)
):
    """
    Removes an image asset from an inspection and cleans up the associated disk file.
    Does not affect unrelated scan_records.
    """
    inspection = db.query(Inspection).filter(Inspection.inspection_id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found."
        )

    image = db.query(InspectionImage).filter(
        InspectionImage.id == image_id,
        InspectionImage.inspection_id == inspection_id
    ).first()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with id {image_id} not found in inspection '{inspection_id}'."
        )

    # Safely remove disk file if owned by this image record
    if image.image_path:
        full_path = BACKEND_DIR / image.image_path
        if full_path.is_file():
            try:
                full_path.unlink()
            except Exception as e:
                logger.warning(f"Could not delete physical file '{full_path}': {e}")

    db.delete(image)
    db.commit()

    return InspectionImageDeleteResponse(
        success=True,
        message=f"Image {image_id} successfully deleted from inspection '{inspection_id}'.",
        image_id=image_id
    )


@router.delete(
    "/{inspection_id}",
    response_model=InspectionDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an inspection and its attached images"
)
def delete_inspection(
    inspection_id: str,
    db: Session = Depends(get_db)
):
    """
    Deletes the inspection and cascades deletion to all attached InspectionImage children.
    Cleans up associated image files on disk. Does not affect unrelated scan_records.
    """
    inspection = db.query(Inspection).filter(Inspection.inspection_id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found."
        )

    # Safely remove associated disk files
    for img in inspection.images:
        if img.image_path:
            full_path = BACKEND_DIR / img.image_path
            if full_path.is_file():
                try:
                    full_path.unlink()
                except Exception as e:
                    logger.warning(f"Could not delete physical file '{full_path}': {e}")

    # Delete parent inspection (cascade deletes InspectionImage rows)
    db.delete(inspection)
    db.commit()

    return InspectionDeleteResponse(
        success=True,
        message=f"Inspection '{inspection_id}' and all associated images successfully deleted.",
        inspection_id=inspection_id
    )


@router.post(
    "/{inspection_id}/process",
    response_model=InspectionProcessResponse,
    status_code=status.HTTP_200_OK,
    summary="Process all inspection images through OCR, extraction, and compliance rules"
)
async def process_inspection(
    inspection_id: str,
    db: Session = Depends(get_db)
):
    """
    Executes complete end-to-end multi-image inspection processing:
    1. Sequentially runs OpenCV preprocessing and RapidOCR on each attached image.
    2. Combines OCR detections across all package views with provenance tags.
    3. Executes structured extraction once on the aggregated text representation.
    4. Evaluates extracted declarations once against statutory Legal Metrology rules.
    5. Persists the unified inspection results and returns the complete compliance audit.
    """
    return await InspectionProcessor.process_inspection(db=db, inspection_id=inspection_id)
