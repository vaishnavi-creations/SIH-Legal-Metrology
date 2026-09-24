from pydantic import BaseModel, Field
from typing import List, Optional
from app.schemas.upload import ImageDimensions

class OCRTextBlock(BaseModel):
    text: str = Field(..., description="Detected text content")
    confidence: float = Field(..., description="Detection confidence score (0.0 to 1.0)")
    polygon: List[List[float]] = Field(..., description="4-point polygon bounding box [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]")
    box_2d: List[int] = Field(..., description="2D rectangular bounding box [x_min, y_min, x_max, y_max]")
    detected_script: str = Field("LATIN", description="Detected script category (LATIN, DEVANAGARI, MIXED, UNKNOWN)")
    script_confidence: float = Field(1.0, description="Confidence of script classification (0.0 to 1.0)")


class OCRResult(BaseModel):
    full_text: str = Field(..., description="Combined extracted text lines separated by newlines")
    blocks: List[OCRTextBlock] = Field(default_factory=list, description="Individual detected text fragments with coordinates")
    block_count: int = Field(..., description="Total number of text fragments detected")
    average_confidence: float = Field(..., description="Average detection confidence across all detected text blocks")
    execution_time_seconds: float = Field(..., description="Total time taken by the OCR engine in seconds")

class OCRProcessResponse(BaseModel):
    success: bool = Field(True, description="Indicates if OCR processing succeeded")
    message: str = Field(..., description="Human-readable status summary")
    file_id: str = Field(..., description="Unique file identifier of the scanned image")
    image_dimensions: ImageDimensions = Field(..., description="Width and height of the image evaluated")
    ocr_result: OCRResult = Field(..., description="Detailed OCR extraction output")
