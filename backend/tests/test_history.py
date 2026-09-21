import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from main import app
from app.db.session import SessionLocal, init_db
from app.db import crud
from app.schemas.product import (
    StructuredProductData,
    MRPDetails,
    NetQuantityDetails,
    DateDetails,
    ManufacturerDetails,
    ConsumerCareDetails
)
from app.schemas.ocr import OCRResult, OCRTextBlock
from app.rules.models import ComplianceReport, ComplianceStatus, Violation, Severity

client = TestClient(app)
SAMPLE_IMAGE_PATH = Path(__file__).resolve().parent.parent.parent / "samples" / "sample_product_label.png"

@pytest.fixture(autouse=True)
def setup_db():
    """Ensure database tables exist before each test."""
    init_db()

def create_dummy_compliance_report(status: ComplianceStatus = ComplianceStatus.COMPLIANT) -> ComplianceReport:
    return ComplianceReport(
        compliance_status=status,
        summary="Test compliance summary",
        rules_checked=8,
        rules_passed=8 if status == ComplianceStatus.COMPLIANT else 6,
        rules_failed=0 if status == ComplianceStatus.COMPLIANT else 2,
        rules_insufficient_data=0,
        rules_not_applicable=0,
        violations=[] if status == ComplianceStatus.COMPLIANT else [
            Violation(
                rule_id="LMR-06-1-E",
                legal_reference="Rule 6(1)(e)",
                field="mrp",
                severity=Severity.HIGH,
                message="Missing retail sale price"
            )
        ],
        warnings=[],
        missing_declarations=[] if status == ComplianceStatus.COMPLIANT else ["mrp"],
        exemptions_applied=[],
        checks=[]
    )

def test_list_history_endpoint():
    """Verify GET /api/history returns valid pagination schema."""
    response = client.get("/api/history?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "items" in data
    assert isinstance(data["items"], list)

def test_crud_and_get_scan_detail():
    """Verify saving a record and retrieving it via GET /api/history/{file_id}."""
    db = SessionLocal()
    file_id = "test-scan-uuid-001"
    try:
        # 1. Clean up if exists
        crud.delete_scan(db, file_id)

        # 2. Insert scan record
        prod = StructuredProductData(
            product_name="Heritage Organic Milk",
            brand="Heritage",
            mrp=MRPDetails(value=32.0, currency="INR", includes_taxes=True),
            net_quantity=NetQuantityDetails(value=500.0, unit="ml")
        )
        ocr = OCRResult(
            full_text="Heritage Organic Milk MRP Rs 32 Net 500ml",
            blocks=[
                OCRTextBlock(
                    text="Heritage Organic Milk",
                    confidence=0.98,
                    polygon=[[10.0, 10.0], [100.0, 10.0], [100.0, 30.0], [10.0, 30.0]],
                    box_2d=[10, 10, 100, 30]
                )
            ],
            block_count=1,
            average_confidence=0.98,
            execution_time_seconds=0.12
        )
        report = create_dummy_compliance_report(ComplianceStatus.COMPLIANT)

        crud.save_or_update_scan(
            db=db,
            file_id=file_id,
            original_filename="heritage_milk.jpg",
            ocr_result=ocr,
            structured_data=prod,
            compliance_report=report
        )
    finally:
        db.close()

    # 3. Retrieve via GET /api/history/{file_id}
    res = client.get(f"/api/history/{file_id}")
    assert res.status_code == 200
    item = res.json()
    assert item["file_id"] == file_id
    assert item["product_name"] == "Heritage Organic Milk"
    assert item["brand"] == "Heritage"
    assert item["mrp"] == 32.0
    assert item["net_quantity"] == "500.0 ml"
    assert item["compliance_status"] == "COMPLIANT"
    assert item["violations_count"] == 0
    assert item["ocr_text"] is not None
    assert len(item["ocr_blocks"]) == 1
    assert item["structured_data"]["brand"] == "Heritage"
    assert item["compliance_report"]["compliance_status"] == "COMPLIANT"

    # Cleanup
    db = SessionLocal()
    try:
        crud.delete_scan(db, file_id)
    finally:
        db.close()

def test_history_filtering_by_status():
    """Verify filtering scan history by COMPLIANT, NON_COMPLIANT, or INSUFFICIENT_DATA."""
    db = SessionLocal()
    fid_comp = "test-comp-scan-101"
    fid_non = "test-noncomp-scan-102"
    fid_insuff = "test-insuff-scan-103"
    try:
        crud.delete_scan(db, fid_comp)
        crud.delete_scan(db, fid_non)
        crud.delete_scan(db, fid_insuff)

        crud.save_or_update_scan(
            db=db,
            file_id=fid_comp,
            original_filename="compliant.png",
            compliance_report=create_dummy_compliance_report(ComplianceStatus.COMPLIANT)
        )
        crud.save_or_update_scan(
            db=db,
            file_id=fid_non,
            original_filename="noncompliant.png",
            compliance_report=create_dummy_compliance_report(ComplianceStatus.NON_COMPLIANT)
        )
        crud.save_or_update_scan(
            db=db,
            file_id=fid_insuff,
            original_filename="insufficient.png",
            compliance_report=create_dummy_compliance_report(ComplianceStatus.INSUFFICIENT_DATA)
        )
    finally:
        db.close()

    # Query status=COMPLIANT
    res_comp = client.get("/api/history?status=COMPLIANT")
    assert res_comp.status_code == 200
    comp_items = res_comp.json()["items"]
    assert all(i["compliance_status"] == "COMPLIANT" for i in comp_items)
    assert any(i["file_id"] == fid_comp for i in comp_items)
    assert not any(i["file_id"] in [fid_non, fid_insuff] for i in comp_items)

    # Query status=NON_COMPLIANT
    res_non = client.get("/api/history?status=NON_COMPLIANT")
    assert res_non.status_code == 200
    non_items = res_non.json()["items"]
    assert all(i["compliance_status"] == "NON_COMPLIANT" for i in non_items)
    assert any(i["file_id"] == fid_non for i in non_items)
    assert not any(i["file_id"] in [fid_comp, fid_insuff] for i in non_items)

    # Query status=INSUFFICIENT_DATA
    res_ins = client.get("/api/history?status=INSUFFICIENT_DATA")
    assert res_ins.status_code == 200
    ins_items = res_ins.json()["items"]
    assert all(i["compliance_status"] == "INSUFFICIENT_DATA" for i in ins_items)
    assert any(i["file_id"] == fid_insuff for i in ins_items)
    assert not any(i["file_id"] in [fid_comp, fid_non] for i in ins_items)

    # Cleanup
    db = SessionLocal()
    try:
        crud.delete_scan(db, fid_comp)
        crud.delete_scan(db, fid_non)
        crud.delete_scan(db, fid_insuff)
    finally:
        db.close()

def test_get_nonexistent_scan_returns_404():
    """Verify requesting a non-existent scan ID returns HTTP 404."""
    res = client.get("/api/history/non-existent-scan-999999")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

def test_delete_scan_record():
    """Verify deleting an existing scan record removes it and handles repeated deletion with 404."""
    db = SessionLocal()
    del_fid = "test-delete-record-303"
    try:
        crud.save_or_update_scan(
            db=db,
            file_id=del_fid,
            original_filename="to_delete.png",
            compliance_report=create_dummy_compliance_report(ComplianceStatus.COMPLIANT)
        )
    finally:
        db.close()

    # 1. Verify exists
    check_res = client.get(f"/api/history/{del_fid}")
    assert check_res.status_code == 200

    # 2. Delete it
    del_res = client.delete(f"/api/history/{del_fid}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # 3. Verify it is gone (404)
    after_del_res = client.get(f"/api/history/{del_fid}")
    assert after_del_res.status_code == 404

    # 4. Deleting again returns 404
    second_del_res = client.delete(f"/api/history/{del_fid}")
    assert second_del_res.status_code == 404

def test_end_to_end_inspection_auto_persists():
    """Verify /api/compliance/inspect-file automatically creates a persistent database record."""
    if not SAMPLE_IMAGE_PATH.exists():
        pytest.skip(f"Sample test image not found at {SAMPLE_IMAGE_PATH}")

    with open(SAMPLE_IMAGE_PATH, "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/api/compliance/inspect-file",
        files={"file": ("sample_product_label.png", file_bytes, "image/png")},
        data={"is_imported": "false", "commodity_type": "food"}
    )
    assert response.status_code == 200
    data = response.json()
    file_id = data["file_id"]
    assert file_id is not None

    # Now verify it is immediately queryable in history
    hist_res = client.get(f"/api/history/{file_id}")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["file_id"] == file_id
    assert hist_data["original_filename"] == "sample_product_label.png"
    assert hist_data["compliance_status"] in ["COMPLIANT", "NON_COMPLIANT", "INSUFFICIENT_DATA"]
    assert hist_data["ocr_text"] is not None
    assert hist_data["structured_data"] is not None
    assert hist_data["compliance_report"] is not None

    # Cleanup
    db = SessionLocal()
    try:
        crud.delete_scan(db, file_id)
    finally:
        db.close()
