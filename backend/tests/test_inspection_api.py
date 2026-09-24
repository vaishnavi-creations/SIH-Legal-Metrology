import io
import cv2
import pytest
import numpy as np
from fastapi.testclient import TestClient

from main import app
from app.db.session import SessionLocal, init_db
from app.db.models import Inspection, InspectionImage, ScanRecord

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure all database tables are initialized before each test."""
    init_db()


def make_test_image_bytes(format: str = "png") -> bytes:
    """Generates valid image bytes in memory using OpenCV for testing."""
    img = np.full((100, 100, 3), 200, dtype=np.uint8)
    # Draw a line so it has some varied pixel content
    cv2.line(img, (10, 10), (90, 90), (0, 0, 255), 2)
    success, buffer = cv2.imencode(f".{format}", img)
    assert success
    return buffer.tobytes()


def test_1_create_inspection():
    """1. Create inspection with all context fields populated."""
    payload = {
        "product_name": "Haldiram's Aloo Bhujia",
        "country_of_manufacture": "India",
        "country_of_sale": "India",
        "is_imported": False,
        "commodity_type": "Packaged Snack",
        "inspection_notes": "Sample verification at retail distribution centre"
    }
    response = client.post("/api/v1/inspections", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert "inspection_id" in data
    assert len(data["inspection_id"]) >= 32
    assert data["product_name"] == "Haldiram's Aloo Bhujia"
    assert data["country_of_manufacture"] == "India"
    assert data["country_of_sale"] == "India"
    assert data["is_imported"] is False
    assert data["commodity_type"] == "Packaged Snack"
    assert data["inspection_notes"] == "Sample verification at retail distribution centre"
    assert data["status"] == "PENDING"
    assert data["image_count"] == 0
    assert "created_at" in data
    assert "updated_at" in data


def test_2_create_inspection_with_default_values():
    """2. Create inspection with empty payload and verify defaults."""
    response = client.post("/api/v1/inspections", json={})
    assert response.status_code == 201
    data = response.json()

    assert "inspection_id" in data
    assert data["product_name"] is None
    assert data["country_of_manufacture"] is None
    assert data["country_of_sale"] is None
    assert data["is_imported"] is False
    assert data["commodity_type"] is None
    assert data["inspection_notes"] is None
    assert data["status"] == "PENDING"
    assert data["image_count"] == 0


def test_3_retrieve_inspection():
    """3. Retrieve an existing inspection by inspection_id."""
    # Create inspection
    create_res = client.post("/api/v1/inspections", json={"product_name": "Amul Butter 500g"})
    assert create_res.status_code == 201
    insp_id = create_res.json()["inspection_id"]

    # Retrieve
    get_res = client.get(f"/api/v1/inspections/{insp_id}")
    assert get_res.status_code == 200
    data = get_res.json()

    assert data["inspection_id"] == insp_id
    assert data["product_name"] == "Amul Butter 500g"
    assert data["image_count"] == 0
    assert data["images"] == []


def test_4_retrieve_unknown_inspection_returns_404():
    """4. Retrieve an unknown inspection_id returns HTTP 404."""
    response = client.get("/api/v1/inspections/non-existent-inspection-id-999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_5_upload_front_image():
    """5. Attach a front image to an existing inspection."""
    # Create inspection
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Tata Tea Gold"})
    insp_id = insp_res.json()["inspection_id"]

    # Upload image
    img_bytes = make_test_image_bytes("jpg")
    response = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("tea_front.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        data={"image_role": "front", "sequence": "1"}
    )
    assert response.status_code == 201
    data = response.json()

    assert data["inspection_id"] == insp_id
    assert data["image_role"] == "front"
    assert data["sequence"] == 1
    assert data["original_filename"] == "tea_front.jpg"
    assert data["file_id"] is not None
    assert data["image_path"] is not None
    assert data["processing_status"] == "PENDING"


def test_6_upload_back_image():
    """6. Attach a back image to an existing inspection."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Nestle Maggi"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_test_image_bytes("png")
    response = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("maggi_back.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "back"}
    )
    assert response.status_code == 201
    data = response.json()

    assert data["inspection_id"] == insp_id
    assert data["image_role"] == "back"
    assert data["original_filename"] == "maggi_back.png"


def test_7_upload_multiple_images_to_same_inspection():
    """7. Attach multiple package images to a single inspection."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Cadbury Bournvita"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_test_image_bytes("png")
    roles = ["front", "back", "label", "top"]
    for role in roles:
        res = client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": (f"{role}.png", io.BytesIO(img_bytes), "image/png")},
            data={"image_role": role}
        )
        assert res.status_code == 201

    # Verify retrieval reflects all images
    get_res = client.get(f"/api/v1/inspections/{insp_id}")
    assert get_res.status_code == 200
    insp_data = get_res.json()

    assert insp_data["image_count"] == 4
    assert len(insp_data["images"]) == 4
    retrieved_roles = [img["image_role"] for img in insp_data["images"]]
    assert set(retrieved_roles) == set(roles)


def test_8_verify_image_ordering_by_sequence():
    """8. Verify attached images are ordered strictly by sequence."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Sequence Order Test"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_test_image_bytes("jpg")

    # Upload out of order: sequence 3, then sequence 1, then sequence 2
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("img3.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        data={"image_role": "bottom", "sequence": "3"}
    )
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("img1.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        data={"image_role": "front", "sequence": "1"}
    )
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("img2.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        data={"image_role": "back", "sequence": "2"}
    )

    get_res = client.get(f"/api/v1/inspections/{insp_id}")
    assert get_res.status_code == 200
    images = get_res.json()["images"]

    assert len(images) == 3
    assert [img["sequence"] for img in images] == [1, 2, 3]
    assert [img["image_role"] for img in images] == ["front", "back", "bottom"]


def test_9_reject_invalid_image_role():
    """9. Rejects unsupported image_role with HTTP 400."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Role Test"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_test_image_bytes("png")
    response = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("pkg.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "invalid_diagonal_angle"}
    )
    assert response.status_code == 400
    assert "invalid image_role" in response.json()["detail"].lower()


def test_10_reject_invalid_image_upload():
    """10. Rejects invalid image upload: empty file, unsupported extension, corrupted bytes."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Upload Validation Test"})
    insp_id = insp_res.json()["inspection_id"]

    # 10a. Empty file
    res_empty = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("empty.png", io.BytesIO(b""), "image/png")},
        data={"image_role": "front"}
    )
    assert res_empty.status_code == 400
    assert "empty" in res_empty.json()["detail"].lower()

    # 10b. Unsupported extension
    res_ext = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("notes.txt", io.BytesIO(b"hello world"), "text/plain")},
        data={"image_role": "front"}
    )
    assert res_ext.status_code == 400
    assert "unsupported file format" in res_ext.json()["detail"].lower()

    # 10c. Corrupted image bytes (valid extension, invalid image content)
    res_corrupt = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("broken.jpg", io.BytesIO(b"NOT_AN_IMAGE_HEADER_BYTES"), "image/jpeg")},
        data={"image_role": "front"}
    )
    assert res_corrupt.status_code == 400
    assert "image validation error" in res_corrupt.json()["detail"].lower()


def test_11_delete_individual_image():
    """11. Delete an individual image from an inspection."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Deletion Test"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_test_image_bytes("png")
    upload_res = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("label.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "label"}
    )
    assert upload_res.status_code == 201
    image_id = upload_res.json()["id"]

    # Delete the image
    del_res = client.delete(f"/api/v1/inspections/{insp_id}/images/{image_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Check inspection has 0 images now
    get_res = client.get(f"/api/v1/inspections/{insp_id}")
    assert get_res.json()["image_count"] == 0
    assert get_res.json()["images"] == []

    # Deleting again returns 404
    del_again = client.delete(f"/api/v1/inspections/{insp_id}/images/{image_id}")
    assert del_again.status_code == 404


def test_12_delete_inspection():
    """12. Delete an inspection and verify it cannot be retrieved."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Temp Inspection"})
    insp_id = insp_res.json()["inspection_id"]

    # Delete inspection
    del_res = client.delete(f"/api/v1/inspections/{insp_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Retrieve returns 404
    get_res = client.get(f"/api/v1/inspections/{insp_id}")
    assert get_res.status_code == 404

    # Second delete returns 404
    del_res2 = client.delete(f"/api/v1/inspections/{insp_id}")
    assert del_res2.status_code == 404


def test_13_verify_cascade_deletion_of_inspection_images():
    """13. Verify that deleting an inspection cascades deletion to all attached InspectionImages."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Cascade Test Product"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_test_image_bytes("jpg")
    img1_res = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("c1.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        data={"image_role": "front"}
    )
    img2_res = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("c2.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        data={"image_role": "back"}
    )
    img1_id = img1_res.json()["id"]
    img2_id = img2_res.json()["id"]

    # Delete parent inspection
    del_res = client.delete(f"/api/v1/inspections/{insp_id}")
    assert del_res.status_code == 200

    # Query DB directly to verify child images are deleted
    db = SessionLocal()
    try:
        orphaned = db.query(InspectionImage).filter(
            InspectionImage.id.in_([img1_id, img2_id])
        ).all()
        assert len(orphaned) == 0
    finally:
        db.close()


def test_14_verify_existing_scan_records_remain_intact():
    """14. Verify that creating and deleting inspections does NOT affect existing scan_records."""
    db = SessionLocal()
    test_file_id = "unaffected-scan-uuid-999"
    try:
        # Create an unrelated scan record in the legacy table
        existing_scan = db.query(ScanRecord).filter(ScanRecord.file_id == test_file_id).first()
        if not existing_scan:
            existing_scan = ScanRecord(
                file_id=test_file_id,
                product_name="Legacy Scan Commodity",
                compliance_status="COMPLIANT"
            )
            db.add(existing_scan)
            db.commit()
    finally:
        db.close()

    # Perform inspection lifecycle operations
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Unrelated Inspection"})
    insp_id = insp_res.json()["inspection_id"]
    img_bytes = make_test_image_bytes("png")
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("unrelated.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "other"}
    )
    client.delete(f"/api/v1/inspections/{insp_id}")

    # Verify the legacy scan_record is completely intact
    db = SessionLocal()
    try:
        scan = db.query(ScanRecord).filter(ScanRecord.file_id == test_file_id).first()
        assert scan is not None
        assert scan.product_name == "Legacy Scan Commodity"
        assert scan.compliance_status == "COMPLIANT"
    finally:
        # Cleanup test record
        db.query(ScanRecord).filter(ScanRecord.file_id == test_file_id).delete()
        db.commit()
        db.close()


def test_15_verify_existing_apis_remain_functional():
    """15. Verify existing APIs (health, history, upload) continue working unchanged."""
    # 15a. Health endpoint
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

    # 15b. History list endpoint
    history_res = client.get("/api/history?page=1&page_size=5")
    assert history_res.status_code == 200
    assert "items" in history_res.json()

    # 15c. Existing scan upload endpoint
    img_bytes = make_test_image_bytes("png")
    upload_res = client.post(
        "/api/scan/upload",
        files={"file": ("test_pkg.png", io.BytesIO(img_bytes), "image/png")}
    )
    assert upload_res.status_code == 201
    assert upload_res.json()["success"] is True
    assert "file_id" in upload_res.json()
