from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

class InspectionCreate(BaseModel):
    product_name: Optional[str] = Field(None, description="Commercial name or title of the packaged commodity")
    country_of_manufacture: Optional[str] = Field(None, description="Country where the commodity was produced or manufactured")
    country_of_sale: Optional[str] = Field(None, description="Country where commodity is offered for retail sale (e.g. India)")
    is_imported: bool = Field(False, description="Flag indicating if the commodity is imported into India")
    commodity_type: Optional[str] = Field(None, description="Category or commodity classification")
    inspection_notes: Optional[str] = Field(None, description="Field inspection notes or auditor comments")


class InspectionImageResponse(BaseModel):
    id: int = Field(..., description="Unique database ID of the image record")
    inspection_id: str = Field(..., description="Parent inspection identifier")
    file_id: Optional[str] = Field(None, description="Unique file UUID associated with this image asset")
    original_filename: Optional[str] = Field(None, description="Original filename of the uploaded image")
    image_path: Optional[str] = Field(None, description="Relative storage path of the uploaded image")
    image_role: str = Field(..., description="Package view role (front, back, left, right, top, bottom, label, other)")
    sequence: int = Field(1, description="Display or processing sequence index")
    processing_status: str = Field("PENDING", description="Image processing and OCR pipeline status")
    uploaded_at: datetime = Field(..., description="Timestamp when the image was uploaded")

    model_config = ConfigDict(from_attributes=True)


class InspectionResponse(BaseModel):
    inspection_id: str = Field(..., description="Unique UUID identifier for the inspection")
    product_name: Optional[str] = Field(None, description="Product commercial name")
    country_of_manufacture: Optional[str] = Field(None, description="Country of manufacture")
    country_of_sale: Optional[str] = Field(None, description="Country of sale")
    is_imported: bool = Field(False, description="Whether the product is imported")
    commodity_type: Optional[str] = Field(None, description="Commodity type")
    inspection_notes: Optional[str] = Field(None, description="Inspection notes")
    status: str = Field(..., description="Current inspection status")
    created_at: datetime = Field(..., description="Timestamp of inspection creation")
    updated_at: datetime = Field(..., description="Timestamp of latest update")
    image_count: int = Field(0, description="Total number of attached product images")

    model_config = ConfigDict(from_attributes=True)


class InspectionDetailResponse(BaseModel):
    inspection_id: str = Field(..., description="Unique UUID identifier for the inspection")
    product_name: Optional[str] = Field(None, description="Product commercial name")
    country_of_manufacture: Optional[str] = Field(None, description="Country of manufacture")
    country_of_sale: Optional[str] = Field(None, description="Country of sale")
    is_imported: bool = Field(False, description="Whether the product is imported")
    commodity_type: Optional[str] = Field(None, description="Commodity type")
    inspection_notes: Optional[str] = Field(None, description="Inspection notes")
    status: str = Field(..., description="Current inspection status")
    created_at: datetime = Field(..., description="Timestamp of inspection creation")
    updated_at: datetime = Field(..., description="Timestamp of latest update")
    image_count: int = Field(0, description="Total number of attached images")
    images: List[InspectionImageResponse] = Field(default_factory=list, description="List of attached packaging images")

    model_config = ConfigDict(from_attributes=True)


class InspectionDeleteResponse(BaseModel):
    success: bool = Field(True, description="Indicates whether the deletion succeeded")
    message: str = Field(..., description="Human-readable deletion result message")
    inspection_id: Optional[str] = Field(None, description="ID of the deleted inspection")


class InspectionImageDeleteResponse(BaseModel):
    success: bool = Field(True, description="Indicates whether the image deletion succeeded")
    message: str = Field(..., description="Human-readable deletion result message")
    image_id: Optional[int] = Field(None, description="ID of the deleted image record")
