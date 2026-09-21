import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.core.config import settings
from app.schemas.upload import ImageDimensions
from app.schemas.ocr import OCRResult
from app.schemas.product import (
    ExtractionRequest,
    ExtractionResponse,
    StructuredProductData
)
from app.ocr.preprocessor import ImagePreprocessor
from app.ocr.ocr_service import OCRService
from app.extractor.gemini_parser import StructuredDataExtractor
from pydantic import BaseModel, Field

router = APIRouter()

class ProcessAllResponse(BaseModel):
    success: bool = Field(True, description="Indicates if end-to-end processing succeeded")
    file_id: str = Field(..., description="Unique scan session ID")
    message: str = Field(..., description="Status message")
    image_dimensions: ImageDimensions = Field(..., description="Processed image dimensions")
    ocr_result: OCRResult = Field(..., description="OCR extracted text and bounding boxes")
    structured_data: StructuredProductData = Field(..., description="Typed product fields extracted by AI/heuristics")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 15 * 1024 * 1024

@router.post(
    "/extract/structured",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    tags=["AI Structured Extraction"],
    summary="Extract structured product fields from raw OCR text",
    description="Takes raw OCR text as input and uses AI (Gemini / Heuristic Engine) to convert it into typed Legal Metrology product declarations."
)
async def extract_structured_from_text(request: ExtractionRequest):
    if not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided text is empty. Cannot extract product fields."
        )

    structured = await StructuredDataExtractor.extract(request.text)

    return ExtractionResponse(
        success=True,
        message="Successfully extracted structured product fields from text.",
        file_id=request.file_id,
        data=structured
    )

@router.post(
    "/extract/by-file-id/{file_id}",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    tags=["AI Structured Extraction"],
    summary="Run OCR and extract structured fields for a previously uploaded image",
    description="Locates the preprocessed image by file_id, executes OCR, and extracts typed Legal Metrology fields."
)
async def extract_structured_by_file_id(file_id: str):
    proc_path = settings.UPLOAD_DIR / "processed" / f"{file_id}_preprocessed.png"
    if not proc_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preprocessed image for file_id '{file_id}' not found."
        )

    # 1. Run OCR
    try:
        ocr_result = OCRService.extract_from_image(proc_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR execution failed: {str(e)}"
        )

    # 2. Extract structured data
    structured = await StructuredDataExtractor.extract(ocr_result.full_text)

    return ExtractionResponse(
        success=True,
        message=f"Extracted product fields from image '{file_id}'.",
        file_id=file_id,
        data=structured
    )

@router.post(
    "/scan/process-all",
    response_model=ProcessAllResponse,
    status_code=status.HTTP_200_OK,
    tags=["AI Structured Extraction"],
    summary="Upload image, run OpenCV preprocessing, OCR, and AI structured extraction",
    description="Unified endpoint executing the complete pipeline: Image -> OpenCV Preprocess -> OCR Text & Boxes -> AI Structured Declarations."
)
async def process_all_steps(file: UploadFile = File(...)):
    # 1. Validate file extension
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{file_ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 2. Read bytes & size check
    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}"
        )

    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty (0 bytes)."
        )

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds limit of {MAX_FILE_SIZE // (1024 * 1024)} MB."
        )

    # 3. OpenCV Preprocessing
    file_id = str(uuid.uuid4())
    try:
        proc_result = ImagePreprocessor.process_and_save(
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
            detail=f"Preprocessing failed: {str(e)}"
        )

    # 4. OCR Extraction
    proc_path = proc_result["processed_saved_path"]
    try:
        ocr_result = OCRService.extract_from_image(proc_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR failed: {str(e)}"
        )

    # 5. Structured Data Extraction
    structured = await StructuredDataExtractor.extract(ocr_result.full_text)

    proc_dims = proc_result["processed_image"]["dimensions"]

    return ProcessAllResponse(
        success=True,
        file_id=file_id,
        message="Successfully processed image: Preprocessing, OCR, and AI Structured Extraction complete.",
        image_dimensions=ImageDimensions(
            width=proc_dims["width"],
            height=proc_dims["height"],
            channels=proc_dims.get("channels", 3)
        ),
        ocr_result=ocr_result,
        structured_data=structured
    )
