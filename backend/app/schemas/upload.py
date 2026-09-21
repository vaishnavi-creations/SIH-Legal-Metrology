from pydantic import BaseModel, Field
from typing import Optional

class ImageDimensions(BaseModel):
    width: int = Field(..., description="Width of the image in pixels")
    height: int = Field(..., description="Height of the image in pixels")
    channels: Optional[int] = Field(None, description="Color channels (e.g. 3 for BGR/RGB, 1 for Grayscale)")

class ProcessedImageDetails(BaseModel):
    file_name: str = Field(..., description="Generated filename for the preprocessed image")
    relative_path: str = Field(..., description="Path relative to the backend uploads directory")
    dimensions: ImageDimensions
    preprocessing_steps_applied: list[str] = Field(default_factory=list, description="List of enhancement techniques applied")

class ImageUploadResponse(BaseModel):
    success: bool = Field(True, description="Indicates if upload and preprocessing succeeded")
    message: str = Field(..., description="Human-readable status summary")
    file_id: str = Field(..., description="Unique identifier for this scan session")
    original_filename: str = Field(..., description="The original name of the uploaded file")
    content_type: str = Field(..., description="MIME type of the uploaded file")
    file_size_bytes: int = Field(..., description="File size in bytes")
    original_dimensions: ImageDimensions
    processed_image: ProcessedImageDetails
