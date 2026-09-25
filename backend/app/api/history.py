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
    items, total = crud.get_unified_history(db, skip=skip, limit=page_size, status_filter=status)

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
    detail = crud.get_unified_detail(db, file_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan record with file_id '{file_id}' not found."
        )
    return detail

@router.delete(
    "/history/{file_id}",
    status_code=status.HTTP_200_OK,
    tags=["Scan History & Audit Logs"],
    summary="Delete a scan record by file_id"
)
def delete_scan_record(file_id: str, db: Session = Depends(get_db)):
    deleted = crud.delete_unified_scan(db, file_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan record with file_id '{file_id}' not found."
        )
    return {"success": True, "message": f"Scan record '{file_id}' successfully deleted."}
