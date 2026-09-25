from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.product import StructuredProductData
from app.rules.models import ComplianceReport

class InspectionCreate(BaseModel):
    product_name: Optional[str] = Field(None, description="Commercial name or title of the packaged commodity")
    country_of_manufacture: Optional[str] = Field(None, description="Country where the commodity was produced or manufactured")
    country_of_sale: Optional[str] = Field(None, description="Country where commodity is offered for retail sale (e.g. India)")
    is_imported: bool = Field(False, description="Flag indicating if the commodity is imported into India")
    commodity_type: Optional[str] = Field(None, description="Category or commodity classification")
    inspection_notes: Optional[str] = Field(None, description="Field inspection notes or auditor comments")
    market_channel: Optional[str] = Field(None, description="Claimed market channel (RETAIL, INSTITUTIONAL, INDUSTRIAL, ECOMMERCE, EXPORT, UNKNOWN)")


class InspectionProcessRequest(BaseModel):
    market_channel: Optional[str] = Field(None, description="Claimed market channel (RETAIL, INSTITUTIONAL, INDUSTRIAL, ECOMMERCE, EXPORT, UNKNOWN)")


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


class ProcessedImageSummary(BaseModel):
    image_id: int = Field(..., description="Database ID of the image record")
    image_role: str = Field(..., description="Package role (front, back, label, etc.)")
    sequence: int = Field(1, description="Sequence order of the image")
    status: str = Field(..., description="Image OCR status: COMPLETED or FAILED")
    ocr_confidence: Optional[float] = Field(None, description="Average OCR detection confidence for this image")
    block_count: int = Field(0, description="Number of text blocks detected on this image")
    error: Optional[str] = Field(None, description="Diagnostic error message if processing failed")


class InspectionOCRBlock(BaseModel):
    image_id: int = Field(..., description="Originating image ID")
    image_role: str = Field(..., description="Originating image role")
    sequence: int = Field(1, description="Image display sequence")
    text: str = Field(..., description="Detected text string")
    confidence: float = Field(..., description="Detection confidence (0.0 to 1.0)")
    polygon: List[List[float]] = Field(..., description="Bounding polygon [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]")
    box_2d: List[int] = Field(..., description="Bounding box [x_min, y_min, x_max, y_max]")
    detected_script: str = Field("LATIN", description="Detected script category (LATIN, DEVANAGARI, MIXED, UNKNOWN)")
    script_confidence: float = Field(1.0, description="Confidence of script classification (0.0 to 1.0)")



class InspectionOCRSummary(BaseModel):
    combined_text: str = Field(..., description="Aggregated normalized OCR text across all images")
    total_blocks: int = Field(..., description="Total text blocks across all images")
    average_confidence: float = Field(0.0, description="Overall OCR average confidence")
    blocks: List[InspectionOCRBlock] = Field(default_factory=list, description="All OCR blocks with source image identity")


class EvidenceSource(BaseModel):
    source_image_id: Optional[int] = Field(None, description="Database ID of the image providing this evidence")
    source_role: Optional[str] = Field(None, description="Package view role (e.g. front, back, label)")
    source_sequence: Optional[int] = Field(None, description="Sequence index of the source image")
    source_text: Optional[str] = Field(None, description="Exact OCR text line or block matching this declaration")
    confidence: Optional[float] = Field(None, description="Detection confidence score (0.0 to 1.0) if measured")
    detected_script: Optional[str] = Field(None, description="Detected script category (LATIN, DEVANAGARI, MIXED, UNKNOWN) if classified")
    extracted_value: Optional[Any] = Field(None, description="Normalized or parsed value extracted from this source")


class FieldConflict(BaseModel):
    field_name: str = Field(..., description="Name of the statutory declaration in conflict (e.g. mrp, net_quantity)")
    competing_values: List[Any] = Field(default_factory=list, description="Contradictory values detected across different views")
    sources: List[EvidenceSource] = Field(default_factory=list, description="Source references corresponding to each competing value")
    conflict_type: str = Field("VALUE_MISMATCH", description="Type of conflict (e.g. VALUE_MISMATCH, UNIT_MISMATCH)")


class FieldProvenance(BaseModel):
    value: Optional[Any] = Field(None, description="Extracted field value")
    source_image_id: Optional[int] = Field(None, description="Database ID of the image providing this evidence")
    source_role: Optional[str] = Field(None, description="Package role where evidence was discovered")
    source_sequence: Optional[int] = Field(None, description="Sequence index of the source image")
    source_text: Optional[str] = Field(None, description="Exact OCR text line or block matching this declaration")
    # Phase 3 Evidence Fusion extensions (backward-compatible defaults)
    is_corroborated: bool = Field(False, description="Flag indicating if declaration was corroborated across multiple views")
    corroborating_sources: List[EvidenceSource] = Field(default_factory=list, description="All sources corroborating this declaration")
    has_conflict: bool = Field(False, description="Flag indicating if competing conflicting evidence was detected for this field")
    conflicts: List[FieldConflict] = Field(default_factory=list, description="List of conflict details for this field")


class InspectionProcessResponse(BaseModel):
    inspection_id: str = Field(..., description="Unique UUID identifier of the inspection")
    status: str = Field(..., description="Overall processing status: COMPLETED or FAILED")
    compliance_status: Optional[str] = Field(None, description="Overall Legal Metrology compliance verdict")
    images_total: int = Field(..., description="Total images attached to inspection")
    images_processed: int = Field(..., description="Number of successfully processed images")
    images: List[ProcessedImageSummary] = Field(default_factory=list, description="Per-image processing diagnostics")
    ocr_summary: InspectionOCRSummary = Field(..., description="Aggregated OCR text and block evidence")
    structured_data: StructuredProductData = Field(..., description="Unified structured declarations from all images")
    compliance_report: ComplianceReport = Field(..., description="Deterministic Legal Metrology compliance evaluation")
    provenance: Dict[str, Optional[FieldProvenance]] = Field(default_factory=dict, description="Declaration-to-image provenance map")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings encountered during processing")
    conflicts: List[FieldConflict] = Field(default_factory=list, description="List of cross-image declaration conflicts detected")
    is_conflicted: bool = Field(False, description="Flag indicating if any field has unresolved competing declarations")
    context_provenance: Optional[Dict[str, Any]] = Field(default=None, description="Context source and conflict diagnostics")
