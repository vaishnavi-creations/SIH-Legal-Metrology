import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class ScanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_id: str
    original_filename: Optional[str] = None
    uploaded_at: datetime.datetime
    product_name: Optional[str] = None
    common_name: Optional[str] = None
    brand: Optional[str] = None
    mrp: Optional[float] = None
    net_quantity: Optional[str] = None
    compliance_status: str
    violations_count: int
    warnings_count: int
    summary: Optional[str] = None
    image_url: Optional[str] = None

class ScanDetail(ScanSummary):
    ocr_text: Optional[str] = None
    ocr_blocks: Optional[List[Dict[str, Any]]] = None
    structured_data: Optional[Dict[str, Any]] = None
    compliance_report: Optional[Dict[str, Any]] = None

class HistoryListResponse(BaseModel):
    total: int = Field(..., description="Total count of scan records")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Items per page")
    items: List[ScanSummary] = Field(default_factory=list, description="List of scan summaries")
