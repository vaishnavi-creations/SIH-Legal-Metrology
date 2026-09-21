import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.core.config import settings
from app.schemas.upload import ImageDimensions
from app.schemas.ocr import OCRProcessResponse
from app.ocr.preprocessor import ImagePreprocessor
from app.ocr.ocr_service import OCRService

router = APIRouter()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB

@router.post(
    "/scan/process-ocr",
    response_model=OCRProcessResponse,
    status_code=status.HTTP_200_OK,
    tags=["OCR Extraction"],
    summary="Upload image and extract text with bounding boxes in one step",
    description="Accepts a product package image, preprocesses it via OpenCV, and extracts all text blocks, confidence scores, and bounding box coordinates using OCR."
)
async def process_and_extract_ocr(file: UploadFile = File(...)):
    # 1. Validate file extension
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
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

    # 4. Preprocess image
    file_id = str(uuid.uuid4())
    try:
        process_result = ImagePreprocessor.process_and_save(
            image_bytes=contents,
            file_id=file_id,
            original_filename=file.filename or "upload.jpg",
            upload_base_dir=settings.UPLOAD_DIR
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image preprocessing failed: {str(e)}"
        )

    # 5. Run OCR on the enhanced preprocessed image
    processed_path = process_result["processed_saved_path"]
    try:
        ocr_result = OCRService.extract_from_image(processed_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR extraction failed: {str(e)}"
        )

    proc_dims = process_result["processed_image"]["dimensions"]

    return OCRProcessResponse(
        success=True,
        message=f"Successfully extracted {ocr_result.block_count} text blocks from package image.",
        file_id=file_id,
        image_dimensions=ImageDimensions(
            width=proc_dims["width"],
            height=proc_dims["height"],
            channels=proc_dims.get("channels", 3)
        ),
        ocr_result=ocr_result
    )

@router.get(
    "/scan/ocr/{file_id}",
    response_model=OCRProcessResponse,
    status_code=status.HTTP_200_OK,
    tags=["OCR Extraction"],
    summary="Run OCR on a previously uploaded image by file_id",
    description="Locates the preprocessed image for the given file_id and performs OCR text extraction."
)
def extract_ocr_by_file_id(file_id: str):
    # Locate preprocessed image
    proc_path = settings.UPLOAD_DIR / "processed" / f"{file_id}_preprocessed.png"
    if not proc_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preprocessed image for file_id '{file_id}' not found. Please upload the image first."
        )

    # Run OCR
    try:
        ocr_result = OCRService.extract_from_image(proc_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR extraction failed: {str(e)}"
        )

    import cv2
    img = cv2.imread(str(proc_path))
    h, w = img.shape[:2] if img is not None else (0, 0)

    return OCRProcessResponse(
        success=True,
        message=f"Successfully extracted {ocr_result.block_count} text blocks from stored image.",
        file_id=file_id,
        image_dimensions=ImageDimensions(width=w, height=h, channels=3),
        ocr_result=ocr_result
    )
