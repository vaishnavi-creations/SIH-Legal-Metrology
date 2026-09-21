import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.core.config import settings
from app.schemas.upload import ImageUploadResponse
from app.ocr.preprocessor import ImagePreprocessor

router = APIRouter()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB

@router.post(
    "/scan/upload",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Scan & Upload"],
    summary="Upload and preprocess a packaged commodity image",
    description="Accepts an image file (JPG, PNG, WEBP), validates size and format, normalizes/enhances it using OpenCV, and stores it for OCR analysis."
)
async def upload_product_image(file: UploadFile = File(...)):
    # 1. Validate file extension
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_ext}'. Allowed formats are: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 2. Validate MIME type
    if file.content_type and file.content_type.lower() not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type '{file.content_type}'. Must be one of: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
        )

    # 3. Read image contents and validate size
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

    # 4. Generate unique file ID
    file_id = str(uuid.uuid4())

    # 5. Process image with OpenCV
    try:
        process_result = ImagePreprocessor.process_and_save(
            image_bytes=contents,
            file_id=file_id,
            original_filename=file.filename or "upload.jpg",
            upload_base_dir=settings.UPLOAD_DIR
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image validation error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image preprocessing failed: {str(e)}"
        )

    return ImageUploadResponse(
        success=True,
        message="Product image successfully uploaded and preprocessed for OCR analysis.",
        file_id=file_id,
        original_filename=file.filename or "unknown",
        content_type=file.content_type or "image/jpeg",
        file_size_bytes=len(contents),
        original_dimensions=process_result["original_dimensions"],
        processed_image=process_result["processed_image"]
    )
