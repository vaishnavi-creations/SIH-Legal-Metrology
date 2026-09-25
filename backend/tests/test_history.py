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


def test_history_lists_legacy_scans_intact():
    """1. Verify legacy ScanRecord rows appear intact in /api/history."""
    import uuid
    db = SessionLocal()
    fid = f"legacy-scan-test-{uuid.uuid4().hex[:8]}"
    try:
        crud.save_or_update_scan(
            db=db,
            file_id=fid,
            original_filename="legacy_sample.jpg",
            structured_data=StructuredProductData(
                product_name="Legacy Tea",
                mrp=MRPDetails(value=150.0),
                net_quantity=NetQuantityDetails(value=500.0, unit="g")
            ),
            compliance_report=create_dummy_compliance_report(ComplianceStatus.COMPLIANT)
        )

        res = client.get("/api/history?page=1&page_size=50")
        assert res.status_code == 200
        data = res.json()
        items = data["items"]
        found = [it for it in items if it["file_id"] == fid]
        assert len(found) == 1
        item = found[0]
        assert item["product_name"] == "Legacy Tea"
        assert item["mrp"] == 150.0
        assert item["compliance_status"] == "COMPLIANT"
        assert item["inspection_type"] == "single"
        assert item["image_count"] == 1
    finally:
        db.query(crud.ScanRecord).filter(crud.ScanRecord.file_id == fid).delete()
        db.commit()
        db.close()


def test_history_lists_completed_multi_image_inspections():
    """2. Verify completed/failed multi-image inspections appear in /api/history."""
    import uuid
    import json
    from app.db.models import Inspection, InspectionImage
    db = SessionLocal()
    insp_id = f"multi-insp-history-test-{uuid.uuid4().hex[:8]}"
    try:
        insp = Inspection(
            inspection_id=insp_id,
            product_name="Multi View Biscuits",
            status="COMPLETED",
            compliance_status="NON_COMPLIANT",
            structured_data_json=json.dumps({
                "product_name": "Multi View Biscuits",
                "mrp": {"value": 45.0, "currency": "INR"},
                "net_quantity": {"value": 200.0, "unit": "g"}
            }),
            compliance_report_json=json.dumps({
                "compliance_status": "NON_COMPLIANT",
                "rules_checked": 8,
                "rules_passed": 7,
                "rules_failed": 1,
                "violations": [{"rule_id": "LMR-01", "legal_reference": "Rule 6", "message": "Missing MRP"}],
                "warnings": []
            }),
            provenance_json=json.dumps({
                "mrp": {"has_conflict": False, "is_corroborated": True}
            })
        )
        db.add(insp)
        db.commit()

        img1 = InspectionImage(
            inspection_id=insp_id,
            file_id=f"img-f-{uuid.uuid4().hex[:6]}",
            image_role="front",
            sequence=1,
            original_filename="front.jpg",
            image_path="uploads/original/front.jpg"
        )
        img2 = InspectionImage(
            inspection_id=insp_id,
            file_id=f"img-b-{uuid.uuid4().hex[:6]}",
            image_role="back",
            sequence=2,
            original_filename="back.jpg",
            image_path="uploads/original/back.jpg"
        )
        db.add(img1)
        db.add(img2)
        db.commit()

        res = client.get("/api/history?page=1&page_size=50")
        assert res.status_code == 200
        data = res.json()
        items = data["items"]
        found = [it for it in items if it["file_id"] == insp_id]
        assert len(found) == 1
        item = found[0]
        assert item["product_name"] == "Multi View Biscuits"
        assert item["mrp"] == 45.0
        assert item["net_quantity"] == "200.0 g"
        assert item["compliance_status"] == "NON_COMPLIANT"
        assert item["violations_count"] == 1
        assert item["inspection_type"] == "multi"
        assert item["image_count"] == 2
        assert "front" in item["image_roles"]
        assert "back" in item["image_roles"]
    finally:
        db.query(InspectionImage).filter(InspectionImage.inspection_id == insp_id).delete()
        db.query(Inspection).filter(Inspection.inspection_id == insp_id).delete()
        db.commit()
        db.close()


def test_history_pagination_and_status_filter_unified():
    """3. Verify status filtering and pagination across unified history."""
    res_compliant = client.get("/api/history?page=1&page_size=20&status=COMPLIANT")
    assert res_compliant.status_code == 200
    comp_items = res_compliant.json()["items"]
    for item in comp_items:
        assert item["compliance_status"] == "COMPLIANT"

    res_non_comp = client.get("/api/history?page=1&page_size=20&status=NON_COMPLIANT")
    assert res_non_comp.status_code == 200
    non_comp_items = res_non_comp.json()["items"]
    for item in non_comp_items:
        assert item["compliance_status"] == "NON_COMPLIANT"


def test_history_get_detail_multi_image():
    """4. Verify GET /api/history/{file_id} resolves a multi-image inspection with full details."""
    import uuid
    import json
    from app.db.models import Inspection, InspectionImage
    db = SessionLocal()
    insp_id = f"multi-detail-test-{uuid.uuid4().hex[:8]}"
    try:
        insp = Inspection(
            inspection_id=insp_id,
            product_name="Detailed Almond Milk",
            status="COMPLETED",
            compliance_status="COMPLIANT",
            structured_data_json=json.dumps({
                "product_name": "Detailed Almond Milk",
                "mrp": {"value": 80.0, "currency": "INR"},
                "net_quantity": {"value": 1.0, "unit": "l"}
            }),
            compliance_report_json=json.dumps({
                "compliance_status": "COMPLIANT",
                "rules_checked": 8,
                "rules_passed": 8,
                "rules_failed": 0,
                "violations": [],
                "warnings": [],
                "checks": [{"rule_id": "LMR-01", "legal_reference": "Rule 6", "field_checked": "mrp", "status": "PASS", "expected_requirement": "MRP required", "explanation": "MRP present"}]
            }),
            ocr_summary_json=json.dumps({
                "combined_text": "Detailed Almond Milk MRP 80 Net 1L",
                "blocks": [{"text": "Detailed Almond Milk", "confidence": 0.98, "sequence": 1, "image_role": "front", "image_id": 1, "polygon": [[0,0],[1,0],[1,1],[0,1]], "box_2d": [0,0,1,1]}]
            }),
            provenance_json=json.dumps({
                "mrp": {"has_conflict": False, "is_corroborated": True, "source_role": "front"}
            })
        )
        db.add(insp)
        db.commit()

        img = InspectionImage(
            inspection_id=insp_id,
            file_id=f"img-detail-{uuid.uuid4().hex[:6]}",
            image_role="front",
            sequence=1,
            original_filename="almond_milk.jpg",
            image_path="uploads/original/almond_milk.jpg"
        )
        db.add(img)
        db.commit()

        res = client.get(f"/api/history/{insp_id}")
        assert res.status_code == 200
        detail = res.json()
        assert detail["file_id"] == insp_id
        assert detail["product_name"] == "Detailed Almond Milk"
        assert detail["compliance_status"] == "COMPLIANT"
        assert detail["inspection_type"] == "multi"
        assert detail["image_count"] == 1
        assert detail["ocr_text"] == "Detailed Almond Milk MRP 80 Net 1L"
        assert len(detail["images"]) == 1
        assert detail["compliance_report"]["rules_passed"] == 8
        assert len(detail["compliance_report"]["checks"]) == 1
        assert detail["provenance"]["mrp"]["is_corroborated"] is True
    finally:
        db.query(InspectionImage).filter(InspectionImage.inspection_id == insp_id).delete()
        db.query(Inspection).filter(Inspection.inspection_id == insp_id).delete()
        db.commit()
        db.close()


def test_history_delete_multi_image():
    """5. Verify DELETE /api/history/{file_id} removes a multi-image inspection."""
    import uuid
    from app.db.models import Inspection, InspectionImage
    db = SessionLocal()
    insp_id = f"multi-delete-test-{uuid.uuid4().hex[:8]}"
    try:
        insp = Inspection(
            inspection_id=insp_id,
            product_name="Temp Delete Inspection",
            status="COMPLETED",
            compliance_status="COMPLIANT"
        )
        db.add(insp)
        db.commit()

        img = InspectionImage(
            inspection_id=insp_id,
            file_id=f"img-del-{uuid.uuid4().hex[:6]}",
            image_role="front",
            sequence=1,
            original_filename="del.jpg"
        )
        db.add(img)
        db.commit()

        # 1. Verify exists in history
        assert client.get(f"/api/history/{insp_id}").status_code == 200

        # 2. Delete it via /api/history/{id}
        del_res = client.delete(f"/api/history/{insp_id}")
        assert del_res.status_code == 200
        assert del_res.json()["success"] is True

        # 3. Verify it returns 404 now
        assert client.get(f"/api/history/{insp_id}").status_code == 404
    finally:
        db.query(InspectionImage).filter(InspectionImage.inspection_id == insp_id).delete()
        db.query(Inspection).filter(Inspection.inspection_id == insp_id).delete()
        db.commit()
        db.close()


def test_history_deterministic_ordering_for_equal_timestamps():
    """6. Verify deterministic ordering when multiple records share the exact same timestamp."""
    import uuid
    import datetime
    from app.db.models import ScanRecord, Inspection
    db = SessionLocal()
    fixed_time = datetime.datetime(2099, 1, 1, 12, 0, 0)
    scan_id = f"det-scan-{uuid.uuid4().hex[:8]}"
    insp_id = f"det-insp-{uuid.uuid4().hex[:8]}"
    try:
        scan = ScanRecord(
            file_id=scan_id,
            product_name="Deterministic Scan",
            uploaded_at=fixed_time,
            compliance_status="COMPLIANT"
        )
        db.add(scan)
        db.commit()

        insp = Inspection(
            inspection_id=insp_id,
            product_name="Deterministic Inspection",
            created_at=fixed_time,
            status="COMPLETED",
            compliance_status="COMPLIANT"
        )
        db.add(insp)
        db.commit()

        # Query multiple times to verify identical deterministic ordering
        res1 = client.get("/api/history?page=1&page_size=10")
        assert res1.status_code == 200
        items1 = [it["file_id"] for it in res1.json()["items"] if it["file_id"] in (scan_id, insp_id)]

        res2 = client.get("/api/history?page=1&page_size=10")
        assert res2.status_code == 200
        items2 = [it["file_id"] for it in res2.json()["items"] if it["file_id"] in (scan_id, insp_id)]

        assert len(items1) == 2
        assert items1 == items2
    finally:
        db.query(ScanRecord).filter(ScanRecord.file_id == scan_id).delete()
        db.query(Inspection).filter(Inspection.inspection_id == insp_id).delete()
        db.commit()
        db.close()


