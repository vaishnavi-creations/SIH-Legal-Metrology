import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db import crud
from app.schemas.history import ScanSummary, ScanDetail, HistoryListResponse

router = APIRouter()

@router.get(
    "/history",
    response_model=HistoryListResponse,
    status_code=status.HTTP_200_OK,
    tags=["Scan History & Audit Logs"],
    summary="Get paginated history of past product package scans",
    description="Returns previous scan records ordered by most recent first, with optional status filtering."
)
def list_scan_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by compliance status (COMPLIANT, NON_COMPLIANT, INSUFFICIENT_DATA)"),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    records, total = crud.get_scans(db, skip=skip, limit=page_size, status_filter=status)

    items = []
    for r in records:
        img_url = f"/uploads/processed/{r.file_id}_preprocessed.png" if r.processed_image_path else None
        items.append(
            ScanSummary(
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
                violations_count=r.violations_count,
                warnings_count=r.warnings_count,
                summary=r.summary,
                image_url=img_url
            )
        )

    return HistoryListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )

@router.get(
    "/history/{file_id}",
    response_model=ScanDetail,
    status_code=status.HTTP_200_OK,
    tags=["Scan History & Audit Logs"],
    summary="Get complete details, OCR blocks, and legal report for a specific scan",
    description="Retrieves the full inspection audit trail for a single scan session by file_id."
)
def get_scan_details(file_id: str, db: Session = Depends(get_db)):
    r = crud.get_scan_by_file_id(db, file_id)
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan record with file_id '{file_id}' not found."
        )

    img_url = f"/uploads/processed/{r.file_id}_preprocessed.png" if r.processed_image_path else None

    ocr_blocks = json.loads(r.ocr_blocks_json) if r.ocr_blocks_json else None
    structured_data = json.loads(r.structured_data_json) if r.structured_data_json else None
    compliance_report = json.loads(r.compliance_report_json) if r.compliance_report_json else None

    return ScanDetail(
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
        violations_count=r.violations_count,
        warnings_count=r.warnings_count,
        summary=r.summary,
        image_url=img_url,
        ocr_text=r.ocr_text,
        ocr_blocks=ocr_blocks,
        structured_data=structured_data,
        compliance_report=compliance_report
    )

@router.delete(
    "/history/{file_id}",
    status_code=status.HTTP_200_OK,
    tags=["Scan History & Audit Logs"],
    summary="Delete a scan record by file_id"
)
def delete_scan_record(file_id: str, db: Session = Depends(get_db)):
    deleted = crud.delete_scan(db, file_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan record with file_id '{file_id}' not found."
        )
    return {"success": True, "message": f"Scan record '{file_id}' successfully deleted."}
