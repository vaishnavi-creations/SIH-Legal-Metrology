import datetime
import json
import logging
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, literal
from app.core.config import BACKEND_DIR
from app.db.models import ScanRecord, Inspection, InspectionImage
from app.schemas.product import StructuredProductData
from app.schemas.ocr import OCRResult
from app.rules.models import ComplianceReport
from app.schemas.history import ScanSummary, ScanDetail

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


def map_scan_record_to_summary(r: ScanRecord) -> ScanSummary:
    img_url = f"/uploads/processed/{r.file_id}_preprocessed.png" if r.processed_image_path else (
        f"/{r.image_path}" if r.image_path else None
    )
    return ScanSummary(
        id=r.id,
        file_id=r.file_id,
        original_filename=r.original_filename,
        uploaded_at=r.uploaded_at,
        product_name=r.product_name,
        common_name=r.common_name,
        brand=r.brand,
        mrp=r.mrp,
        net_quantity=r.net_quantity,
        compliance_status=r.compliance_status,
        violations_count=r.violations_count or 0,
        warnings_count=r.warnings_count or 0,
        summary=r.summary,
        image_url=img_url,
        inspection_type="single",
        image_count=1,
        image_roles=["label"],
        is_conflicted=False,
        is_imported=False,
        commodity_type=None
    )


def map_inspection_to_summary(inspection: Inspection) -> ScanSummary:
    structured_data = {}
    if inspection.structured_data_json:
        try:
            structured_data = json.loads(inspection.structured_data_json)
        except Exception:
            structured_data = {}

    compliance_report = {}
    if inspection.compliance_report_json:
        try:
            compliance_report = json.loads(inspection.compliance_report_json)
        except Exception:
            compliance_report = {}

    provenance = {}
    if inspection.provenance_json:
        try:
            provenance = json.loads(inspection.provenance_json)
        except Exception:
            provenance = {}

    images = inspection.images or []
    image_count = len(images)
    image_roles = [img.image_role for img in images]

    primary_img = None
    if images:
        front_imgs = [img for img in images if img.image_role == "front"]
        if front_imgs:
            primary_img = front_imgs[0]
        else:
            primary_img = sorted(images, key=lambda x: x.sequence)[0]

    image_url = f"/{primary_img.image_path}" if (primary_img and primary_img.image_path) else None
    original_filename = (
        primary_img.original_filename
        if (primary_img and primary_img.original_filename)
        else f"Inspection {inspection.inspection_id[:8]}"
    )

    prod_name = (
        inspection.product_name
        or structured_data.get("product_name")
        or structured_data.get("common_or_generic_name")
        or original_filename
    )
    common_name = structured_data.get("common_or_generic_name")
    brand = structured_data.get("brand")

    mrp_val = None
    mrp_data = structured_data.get("mrp")
    if isinstance(mrp_data, dict):
        mrp_val = mrp_data.get("value")
    elif isinstance(mrp_data, (int, float)):
        mrp_val = float(mrp_data)

    net_qty_val = None
    net_qty_data = structured_data.get("net_quantity")
    if isinstance(net_qty_data, dict):
        val = net_qty_data.get("value")
        unit = net_qty_data.get("unit") or ""
        if val is not None:
            net_qty_val = f"{val} {unit}".strip()
    elif isinstance(net_qty_data, str):
        net_qty_val = net_qty_data

    comp_status = inspection.compliance_status or "INSUFFICIENT_DATA"
    violations_count = compliance_report.get("rules_failed", 0)
    warnings_list = compliance_report.get("warnings", [])
    warnings_count = len(warnings_list) if isinstance(warnings_list, list) else 0

    is_conflicted = False
    for field_prov in provenance.values():
        if isinstance(field_prov, dict) and field_prov.get("has_conflict"):
            is_conflicted = True
            break

    uploaded_at = inspection.created_at or datetime.datetime.now(datetime.timezone.utc)

    return ScanSummary(
        id=inspection.id,
        file_id=inspection.inspection_id,
        original_filename=original_filename,
        uploaded_at=uploaded_at,
        product_name=prod_name,
        common_name=common_name,
        brand=brand,
        mrp=mrp_val,
        net_quantity=net_qty_val,
        compliance_status=comp_status,
        violations_count=violations_count,
        warnings_count=warnings_count,
        summary=compliance_report.get("summary") or inspection.inspection_notes,
        image_url=image_url,
        inspection_type="multi",
        image_count=image_count,
        image_roles=image_roles,
        is_conflicted=is_conflicted,
        is_imported=inspection.is_imported,
        commodity_type=inspection.commodity_type
    )


def map_scan_record_to_detail(r: ScanRecord) -> ScanDetail:
    summary = map_scan_record_to_summary(r)
    ocr_blocks = json.loads(r.ocr_blocks_json) if r.ocr_blocks_json else None
    structured_data = json.loads(r.structured_data_json) if r.structured_data_json else None
    compliance_report = json.loads(r.compliance_report_json) if r.compliance_report_json else None

    return ScanDetail(
        id=summary.id,
        file_id=summary.file_id,
        original_filename=summary.original_filename,
        uploaded_at=summary.uploaded_at,
        product_name=summary.product_name,
        common_name=summary.common_name,
        brand=summary.brand,
        mrp=summary.mrp,
        net_quantity=summary.net_quantity,
        compliance_status=summary.compliance_status,
        violations_count=summary.violations_count,
        warnings_count=summary.warnings_count,
        summary=summary.summary,
        image_url=summary.image_url,
        inspection_type="single",
        image_count=1,
        image_roles=["label"],
        is_conflicted=False,
        is_imported=False,
        commodity_type=None,
        ocr_text=r.ocr_text,
        ocr_blocks=ocr_blocks,
        structured_data=structured_data,
        compliance_report=compliance_report,
        provenance={},
        conflicts=[],
        images=[],
        warnings=[]
    )


def map_inspection_to_detail(inspection: Inspection) -> ScanDetail:
    summary = map_inspection_to_summary(inspection)

    ocr_summary = {}
    if inspection.ocr_summary_json:
        try:
            ocr_summary = json.loads(inspection.ocr_summary_json)
        except Exception:
            pass

    structured_data = None
    if inspection.structured_data_json:
        try:
            structured_data = json.loads(inspection.structured_data_json)
        except Exception:
            pass

    compliance_report = None
    if inspection.compliance_report_json:
        try:
            compliance_report = json.loads(inspection.compliance_report_json)
        except Exception:
            pass

    provenance = None
    if inspection.provenance_json:
        try:
            provenance = json.loads(inspection.provenance_json)
        except Exception:
            pass

    images_list = []
    for img in sorted(inspection.images or [], key=lambda x: x.sequence):
        images_list.append({
            "id": img.id,
            "file_id": img.file_id,
            "original_filename": img.original_filename,
            "image_path": f"/{img.image_path}" if img.image_path else None,
            "image_role": img.image_role,
            "sequence": img.sequence,
            "processing_status": img.processing_status
        })

    conflicts_list = []
    if provenance:
        for f_name, p_info in provenance.items():
            if isinstance(p_info, dict) and p_info.get("conflicts"):
                for c in p_info["conflicts"]:
                    conflicts_list.append(c)

    return ScanDetail(
        id=summary.id,
        file_id=summary.file_id,
        original_filename=summary.original_filename,
        uploaded_at=summary.uploaded_at,
        product_name=summary.product_name,
        common_name=summary.common_name,
        brand=summary.brand,
        mrp=summary.mrp,
        net_quantity=summary.net_quantity,
        compliance_status=summary.compliance_status,
        violations_count=summary.violations_count,
        warnings_count=summary.warnings_count,
        summary=summary.summary,
        image_url=summary.image_url,
        inspection_type=summary.inspection_type,
        image_count=summary.image_count,
        image_roles=summary.image_roles,
        is_conflicted=summary.is_conflicted,
        is_imported=summary.is_imported,
        commodity_type=summary.commodity_type,
        ocr_text=ocr_summary.get("combined_text") or "",
        ocr_blocks=ocr_summary.get("blocks") or [],
        structured_data=structured_data,
        compliance_report=compliance_report,
        provenance=provenance,
        conflicts=conflicts_list,
        images=images_list,
        warnings=[]
    )


def get_unified_history(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None
) -> Tuple[List[ScanSummary], int]:
    """
    Retrieves paginated scan records across both legacy single-image scans (ScanRecord)
    and completed multi-image inspections (Inspection), merged and sorted chronologically
    by upload/creation time descending.
    """
    q1 = db.query(
        ScanRecord.id.label("id"),
        ScanRecord.file_id.label("file_id"),
        ScanRecord.uploaded_at.label("uploaded_at"),
        literal("single").label("kind")
    )
    if status_filter and status_filter.upper() != "ALL":
        q1 = q1.filter(ScanRecord.compliance_status == status_filter.upper())

    q2 = db.query(
        Inspection.id.label("id"),
        Inspection.inspection_id.label("file_id"),
        Inspection.created_at.label("uploaded_at"),
        literal("multi").label("kind")
    ).filter(Inspection.status.in_(["COMPLETED", "FAILED"]))
    if status_filter and status_filter.upper() != "ALL":
        q2 = q2.filter(Inspection.compliance_status == status_filter.upper())

    total = q1.count() + q2.count()
    union_q = q1.union_all(q2).order_by(desc("uploaded_at"), desc("id"), desc("file_id"))
    rows = union_q.offset(skip).limit(limit).all()

    if not rows:
        return [], total

    scan_ids = [r.id for r in rows if r.kind == "single"]
    insp_ids = [r.id for r in rows if r.kind == "multi"]

    scans_map = {}
    if scan_ids:
        scans_map = {s.id: s for s in db.query(ScanRecord).filter(ScanRecord.id.in_(scan_ids)).all()}

    insps_map = {}
    if insp_ids:
        insps_map = {i.id: i for i in db.query(Inspection).filter(Inspection.id.in_(insp_ids)).all()}

    items: List[ScanSummary] = []
    for r in rows:
        if r.kind == "single":
            record = scans_map.get(r.id)
            if record:
                items.append(map_scan_record_to_summary(record))
        elif r.kind == "multi":
            inspection = insps_map.get(r.id)
            if inspection:
                items.append(map_inspection_to_summary(inspection))

    return items, total


def get_unified_detail(db: Session, file_id: str) -> Optional[ScanDetail]:
    """
    Retrieves deep audit details for either a legacy single-image ScanRecord
    or a multi-image Inspection session by identifier.
    """
    # 1. Check legacy ScanRecord first
    r = db.query(ScanRecord).filter(ScanRecord.file_id == file_id).first()
    if r:
        return map_scan_record_to_detail(r)

    # 2. Check multi-image Inspection
    insp = db.query(Inspection).filter(Inspection.inspection_id == file_id).first()
    if insp:
        return map_inspection_to_detail(insp)

    return None


def delete_unified_scan(db: Session, file_id: str) -> bool:
    """
    Safely deletes either a legacy ScanRecord or a multi-image Inspection session.
    Cascades attached images and cleans up physical files on disk.
    """
    # 1. Check legacy ScanRecord first
    r = db.query(ScanRecord).filter(ScanRecord.file_id == file_id).first()
    if r:
        return delete_scan(db, file_id)

    # 2. Check multi-image Inspection
    insp = db.query(Inspection).filter(Inspection.inspection_id == file_id).first()
    if insp:
        for img in insp.images:
            if img.image_path:
                full_path = BACKEND_DIR / img.image_path
                if full_path.is_file():
                    try:
                        full_path.unlink()
                    except Exception as e:
                        logger.warning(f"Could not delete physical file '{full_path}': {e}")
        db.delete(insp)
        db.commit()
        return True

    return False

