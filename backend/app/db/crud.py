import json
import logging
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.models import ScanRecord
from app.schemas.product import StructuredProductData
from app.schemas.ocr import OCRResult
from app.rules.models import ComplianceReport

logger = logging.getLogger(__name__)

def save_or_update_scan(
    db: Session,
    file_id: str,
    original_filename: Optional[str] = None,
    image_path: Optional[str] = None,
    processed_image_path: Optional[str] = None,
    ocr_result: Optional[OCRResult] = None,
    structured_data: Optional[StructuredProductData] = None,
    compliance_report: Optional[ComplianceReport] = None
) -> ScanRecord:
    """
    Creates or updates an inspection record in SQLite.
    Stores structured summary fields for fast retrieval, plus serialized JSON payloads.
    """
    record = db.query(ScanRecord).filter(ScanRecord.file_id == file_id).first()

    if not record:
        record = ScanRecord(file_id=file_id)
        db.add(record)

    if original_filename:
        record.original_filename = original_filename
    if image_path:
        record.image_path = image_path
    if processed_image_path:
        record.processed_image_path = processed_image_path

    if ocr_result:
        record.ocr_text = ocr_result.full_text
        record.ocr_blocks_json = json.dumps([b.model_dump() for b in ocr_result.blocks])

    if structured_data:
        record.product_name = structured_data.product_name or structured_data.common_or_generic_name
        record.common_name = structured_data.common_or_generic_name
        record.brand = structured_data.brand
        if structured_data.mrp and structured_data.mrp.value is not None:
            record.mrp = structured_data.mrp.value
        if structured_data.net_quantity and structured_data.net_quantity.value is not None:
            unit_str = structured_data.net_quantity.unit or ""
            record.net_quantity = f"{structured_data.net_quantity.value} {unit_str}".strip()
        record.structured_data_json = structured_data.model_dump_json()

    if compliance_report:
        record.compliance_status = compliance_report.compliance_status.value
        record.violations_count = compliance_report.rules_failed
        record.warnings_count = len(compliance_report.warnings)
        record.summary = compliance_report.summary
        record.compliance_report_json = compliance_report.model_dump_json()

    db.commit()
    db.refresh(record)
    return record

def get_scan_by_file_id(db: Session, file_id: str) -> Optional[ScanRecord]:
    """Retrieves a single scan record by file_id."""
    return db.query(ScanRecord).filter(ScanRecord.file_id == file_id).first()

def get_scans(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None
) -> Tuple[List[ScanRecord], int]:
    """
    Retrieves paginated scan records ordered by upload time descending.
    Optionally filters by compliance_status (e.g. COMPLIANT, NON_COMPLIANT).
    """
    query = db.query(ScanRecord)
    if status_filter:
        query = query.filter(ScanRecord.compliance_status == status_filter.upper())

    total = query.count()
    items = query.order_by(desc(ScanRecord.uploaded_at)).offset(skip).limit(limit).all()
    return items, total

def delete_scan(db: Session, file_id: str) -> bool:
    """Deletes a scan record by file_id. Returns True if deleted, False if not found."""
    record = db.query(ScanRecord).filter(ScanRecord.file_id == file_id).first()
    if record:
        db.delete(record)
        db.commit()
        return True
    return False
