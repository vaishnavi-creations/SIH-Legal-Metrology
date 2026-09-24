import io
import json
import cv2
import pytest
from pathlib import Path
import numpy as np
from unittest.mock import patch
from fastapi.testclient import TestClient

from main import app
from app.core.config import BACKEND_DIR
from app.db.session import SessionLocal, init_db
from tests.test_ocr import create_synthetic_devanagari_image

SAMPLE_IMAGE_PATH = Path(__file__).resolve().parent.parent.parent / "samples" / "sample_product_label.png"
from app.db.models import Inspection, InspectionImage
from app.ocr.ocr_service import OCRService
from app.schemas.ocr import OCRResult, OCRTextBlock
from app.rules.models import ComplianceStatus

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def make_dummy_image_bytes(format: str = "png") -> bytes:
    """Generates valid image bytes in memory using OpenCV."""
    img = np.full((150, 150, 3), 220, dtype=np.uint8)
    cv2.putText(img, "TEST", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    success, buffer = cv2.imencode(f".{format}", img)
    assert success
    return buffer.tobytes()


def make_ocr_result(lines: list[str], confidence: float = 0.95) -> OCRResult:
    """Creates a mock OCRResult with blocks and full text."""
    blocks = []
    full_text = "\n".join(lines)
    for idx, line in enumerate(lines):
        blocks.append(
            OCRTextBlock(
                text=line,
                confidence=confidence,
                polygon=[[10.0, 10.0 + idx * 25], [250.0, 10.0 + idx * 25], [250.0, 30.0 + idx * 25], [10.0, 30.0 + idx * 25]],
                box_2d=[10, 10 + idx * 25, 250, 30 + idx * 25]
            )
        )
    return OCRResult(
        full_text=full_text,
        blocks=blocks,
        block_count=len(blocks),
        average_confidence=confidence,
        execution_time_seconds=0.04
    )


def test_1_process_inspection_with_one_image():
    """1. Process inspection with one valid image."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Single Image Biscuit"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_dummy_image_bytes("png")
    upload_res = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("front.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "front"}
    )
    assert upload_res.status_code == 201

    mock_ocr = make_ocr_result([
        "Britannia Marie Gold",
        "MRP Rs 30.00 (incl of all taxes)",
        "Net Qty: 200 g"
    ])

    with patch.object(OCRService, "extract_from_image", return_value=mock_ocr):
        proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")

    assert proc_res.status_code == 200
    data = proc_res.json()
    assert data["inspection_id"] == insp_id
    assert data["status"] == "COMPLETED"
    assert data["images_total"] == 1
    assert data["images_processed"] == 1
    assert len(data["images"]) == 1
    assert data["images"][0]["status"] == "COMPLETED"
    assert data["images"][0]["image_role"] == "front"


def test_2_process_inspection_with_front_and_back():
    """2. Process inspection with front + back images."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Dual View Chocolate"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_dummy_image_bytes("jpg")
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("front.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        data={"image_role": "front", "sequence": "1"}
    )
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("back.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        data={"image_role": "back", "sequence": "2"}
    )

    ocr_front = make_ocr_result(["Cadbury Dairy Milk", "MRP Rs. 50 (incl. of all taxes)"])
    ocr_back = make_ocr_result([
        "Net Weight: 100g",
        "Mfg Date: 02/2024",
        "Best Before: 9 Months",
        "Manufactured by: Mondelez India Foods Pvt Ltd, Mumbai 400018",
        "Consumer Care: 1800-22-7080, consumer@mdlz.com",
        "Country of Origin: India"
    ])

    def mock_extract(img_input):
        # Return front or back based on call order or inspection
        return ocr_front if getattr(mock_extract, "called_once", False) is False else ocr_back

    def side_effect(img_input):
        if not hasattr(side_effect, "call_count"):
            side_effect.call_count = 0
        side_effect.call_count += 1
        return ocr_front if side_effect.call_count == 1 else ocr_back

    with patch.object(OCRService, "extract_from_image", side_effect=side_effect):
        proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")

    assert proc_res.status_code == 200
    data = proc_res.json()
    assert data["status"] == "COMPLETED"
    assert data["images_total"] == 2
    assert data["images_processed"] == 2
    roles = [img["image_role"] for img in data["images"]]
    assert roles == ["front", "back"]


def test_3_process_inspection_with_four_images():
    """3. Process inspection with four package views (front, back, left, right)."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Cube Box Commodity"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_dummy_image_bytes("png")
    roles = ["front", "back", "left", "right"]
    for idx, role in enumerate(roles, 1):
        client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": (f"{role}.png", io.BytesIO(img_bytes), "image/png")},
            data={"image_role": role, "sequence": str(idx)}
        )

    def side_effect(img):
        return make_ocr_result([f"Sample declaration on face"])

    with patch.object(OCRService, "extract_from_image", side_effect=side_effect):
        proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")

    assert proc_res.status_code == 200
    data = proc_res.json()
    assert data["images_total"] == 4
    assert data["images_processed"] == 4
    for role in roles:
        assert f"--- {role.upper()} ---" in data["ocr_summary"]["combined_text"]


def test_4_ocr_provenance_is_preserved():
    """4. Verify declaration-to-image provenance correctly identifies source view."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Provenance Test"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_dummy_image_bytes("png")
    front_up = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("front.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "front", "sequence": "1"}
    )
    back_up = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("back.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "back", "sequence": "2"}
    )
    front_id = front_up.json()["id"]
    back_id = back_up.json()["id"]

    ocr_front = make_ocr_result(["Parle-G Gold", "MRP Rs. 25.00 (inclusive of all taxes)"])
    ocr_back = make_ocr_result([
        "Net Qty: 150g",
        "Mfg Date: 03/2024",
        "Manufactured by: Parle Products Pvt Ltd, Mumbai 400057",
        "Consumer Care: 1800-22-1111, care@parle.biz"
    ])

    def side_effect(img):
        if not hasattr(side_effect, "count"):
            side_effect.count = 0
        side_effect.count += 1
        return ocr_front if side_effect.count == 1 else ocr_back

    with patch.object(OCRService, "extract_from_image", side_effect=side_effect):
        proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")

    assert proc_res.status_code == 200
    prov = proc_res.json()["provenance"]

    # MRP must point to front image
    assert prov["mrp"] is not None
    assert prov["mrp"]["source_role"] == "front"
    assert prov["mrp"]["source_image_id"] == front_id

    # Manufacturer must point to back image
    assert prov["manufacturer"] is not None
    assert prov["manufacturer"]["source_role"] == "back"
    assert prov["manufacturer"]["source_image_id"] == back_id


def test_5_ocr_results_from_all_images_are_aggregated():
    """5. Verify OCR results from all images are combined into unified evidence."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Aggregation Test"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_dummy_image_bytes("png")
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("front.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "front"}
    )
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("back.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "back"}
    )

    ocr1 = make_ocr_result(["Front Line 1", "Front Line 2"])
    ocr2 = make_ocr_result(["Back Line 1", "Back Line 2", "Back Line 3"])

    def side_effect(img):
        if not hasattr(side_effect, "count"):
            side_effect.count = 0
        side_effect.count += 1
        return ocr1 if side_effect.count == 1 else ocr2

    with patch.object(OCRService, "extract_from_image", side_effect=side_effect):
        proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")

    assert proc_res.status_code == 200
    summary = proc_res.json()["ocr_summary"]
    # Total blocks should be 2 + 3 = 5
    assert summary["total_blocks"] == 5
    assert len(summary["blocks"]) == 5
    roles_in_blocks = {b["image_role"] for b in summary["blocks"]}
    assert roles_in_blocks == {"front", "back"}


def test_6_structured_extraction_receives_combined_evidence():
    """6. Verify structured extraction receives information distributed across images."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Split Evidence Product"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_dummy_image_bytes("png")
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("f.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "front"}
    )
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("b.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "back"}
    )

    ocr_front = make_ocr_result(["MRP Rs. 99.00 (inclusive of all taxes)"])
    ocr_back = make_ocr_result(["Net Qty: 450 g"])

    def side_effect(img):
        if not hasattr(side_effect, "count"):
            side_effect.count = 0
        side_effect.count += 1
        return ocr_front if side_effect.count == 1 else ocr_back

    with patch.object(OCRService, "extract_from_image", side_effect=side_effect):
        proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")

    assert proc_res.status_code == 200
    structured = proc_res.json()["structured_data"]
    assert structured["mrp"]["value"] == 99.0
    assert structured["net_quantity"]["value"] == 450.0


def test_7_compliance_engine_receives_one_unified_product():
    """7. Compliance engine evaluates the UNION of declarations as ONE package."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Compliant Multi-View Cookie"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_dummy_image_bytes("png")
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("f.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "front"}
    )
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("b.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "back"}
    )

    # Front only has Brand, Generic name, and MRP
    ocr_front = make_ocr_result([
        "NUTRI-CRUNCH ALMOND COOKIES",
        "Common/Generic Name: Baked Oat Cookies",
        "MRP: Rs. 55.00 (inclusive of all taxes)"
    ])
    # Back has remaining mandatory declarations
    ocr_back = make_ocr_result([
        "Net Quantity: 200 g (Unit Sale Price: Rs. 0.275/g)",
        "Month & Year of Manufacture: 08/2026",
        "Best Before: 6 Months from date of packaging",
        "Manufactured & Packed by: Organic Foods India Pvt Ltd",
        "Factory Address: Plot 42, KIADB Industrial Area, Bengaluru - 560066",
        "Consumer Care: Email: care@nutricrunch.com | Toll Free: 1800-200-1122",
        "Country of Origin: India",
        "Batch No: BATCH-NC-8842"
    ])

    def side_effect(img):
        if not hasattr(side_effect, "count"):
            side_effect.count = 0
        side_effect.count += 1
        return ocr_front if side_effect.count == 1 else ocr_back

    with patch.object(OCRService, "extract_from_image", side_effect=side_effect):
        proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")

    assert proc_res.status_code == 200
    report = proc_res.json()["compliance_report"]
    # Unified evaluation must be COMPLIANT because front + back satisfy all rules
    assert report["compliance_status"] == ComplianceStatus.COMPLIANT.value
    assert report["rules_failed"] == 0
    assert len(report["violations"]) == 0


def test_8_missing_inspection_returns_404():
    """8. Missing inspection_id returns HTTP 404."""
    response = client.post("/api/v1/inspections/non-existent-uuid-12345/process")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_9_inspection_with_zero_images_returns_400():
    """9. Inspection with zero images returns HTTP 400."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Zero Image Inspection"})
    insp_id = insp_res.json()["inspection_id"]

    response = client.post(f"/api/v1/inspections/{insp_id}/process")
    assert response.status_code == 400
    assert "no attached packaging images" in response.json()["detail"].lower()


def test_10_missing_or_corrupted_image_handled_safely():
    """10. Missing or corrupt image is handled safely without unhandled 500 error."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Corrupted Image Inspection"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_dummy_image_bytes("png")
    upload_res = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("front.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "front"}
    )
    image_path_str = upload_res.json()["image_path"]

    # Intentionally corrupt the saved file on disk
    full_path = BACKEND_DIR / image_path_str
    with open(full_path, "wb") as f:
        f.write(b"CORRUPTED_NON_IMAGE_DATA_BYTES")

    proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")
    assert proc_res.status_code == 200
    data = proc_res.json()
    assert data["status"] == "FAILED"
    assert data["images"][0]["status"] == "FAILED"
    assert len(data["warnings"]) > 0


def test_11_one_failed_image_does_not_erase_successful_evidence():
    """11. One failed image does not erase successful image evidence."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Partial Failure Test"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_dummy_image_bytes("png")
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("good.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "front"}
    )
    bad_upload = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("bad.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "back"}
    )

    # Corrupt only the second image file
    bad_path = BACKEND_DIR / bad_upload.json()["image_path"]
    with open(bad_path, "wb") as f:
        f.write(b"BAD_CORRUPT")

    ocr_good = make_ocr_result(["MRP Rs. 75.00 (inclusive of all taxes)"])
    with patch.object(OCRService, "extract_from_image", return_value=ocr_good):
        proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")

    assert proc_res.status_code == 200
    data = proc_res.json()
    assert data["images_total"] == 2
    assert data["images_processed"] == 1
    # Evidence from good image is preserved
    assert data["structured_data"]["mrp"]["value"] == 75.0
    assert len(data["warnings"]) > 0
    # Inspection completes with available evidence
    assert data["status"] == "COMPLETED"


def test_12_all_image_processing_failures_produce_non_successful_state():
    """12. All image processing failures produce a non-successful inspection state."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "All Fail Test"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_dummy_image_bytes("png")
    u1 = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("i1.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "front"}
    )
    u2 = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("i2.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "back"}
    )

    # Delete both physical files
    (BACKEND_DIR / u1.json()["image_path"]).unlink()
    (BACKEND_DIR / u2.json()["image_path"]).unlink()

    proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")
    assert proc_res.status_code == 200
    data = proc_res.json()
    assert data["status"] == "FAILED"
    assert data["compliance_status"] == "INSUFFICIENT_DATA"
    assert data["images_processed"] == 0
    assert len(data["warnings"]) >= 2


def make_multilingual_ocr_result(lines_with_scripts: list[tuple[str, str, float]], confidence: float = 0.95) -> OCRResult:
    """Creates a mock OCRResult where each block has explicit text, detected_script, and confidence."""
    blocks = []
    text_lines = [item[0] for item in lines_with_scripts]
    full_text = "\n".join(text_lines)
    for idx, (line, script, conf) in enumerate(lines_with_scripts):
        blocks.append(
            OCRTextBlock(
                text=line,
                confidence=conf,
                polygon=[[10.0, 10.0 + idx * 25], [250.0, 10.0 + idx * 25], [250.0, 30.0 + idx * 25], [10.0, 30.0 + idx * 25]],
                box_2d=[10, 10 + idx * 25, 250, 30 + idx * 25],
                detected_script=script,
                script_confidence=1.0 if script in {"LATIN", "DEVANAGARI"} else 0.8
            )
        )
    return OCRResult(
        full_text=full_text,
        blocks=blocks,
        block_count=len(blocks),
        average_confidence=confidence,
        execution_time_seconds=0.04
    )


def test_13_multilingual_front_english_back_devanagari_inspection():
    """13. Multi-image mixed-language: Front in English, Back in Devanagari (Hindi)."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Himalayan Pure Honey"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_dummy_image_bytes("png")
    front_up = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("front.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "front", "sequence": "1"}
    )
    back_up = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("back.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "back", "sequence": "2"}
    )
    assert front_up.status_code == 201
    assert back_up.status_code == 201
    front_id = front_up.json()["id"]
    back_id = back_up.json()["id"]

    ocr_front = make_multilingual_ocr_result([
        ("Himalayan Pure Honey", "LATIN", 0.98),
        ("Common Name: Natural Honey", "LATIN", 0.96),
        ("Country of Origin: India", "LATIN", 0.95),
        ("Batch No: HON-2026-99", "LATIN", 0.94),
    ])

    ocr_back = make_multilingual_ocr_result([
        ("अधिकतम खुदरा मूल्य ₹250 (सभी करों सहित)", "DEVANAGARI", 0.95),
        ("इकाई बिक्री मूल्य: Rs. 0.50 / g", "DEVANAGARI", 0.95),
        ("शुद्ध मात्रा 500 ग्राम", "DEVANAGARI", 0.94),
        ("निर्माण तिथि: 07/2026", "DEVANAGARI", 0.96),
        ("उपयोग की अवधि: 18 माह", "DEVANAGARI", 0.92),
        ("निर्माता: हिमालयन एग्रो फूड्स प्रा. लि.", "DEVANAGARI", 0.93),
        ("कारखाना का पता: 45 इंडस्ट्रियल एस्टेट, शिमला - 171001", "DEVANAGARI", 0.91),
        ("उपभोक्ता देखभाल: 1800-444-5555 | care@himalayanagro.in", "DEVANAGARI", 0.95),
    ])

    def side_effect(img):
        if not hasattr(side_effect, "count"):
            side_effect.count = 0
        side_effect.count += 1
        return ocr_front if side_effect.count == 1 else ocr_back

    with patch.object(OCRService, "extract_from_image", side_effect=side_effect):
        proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")

    assert proc_res.status_code == 200
    data = proc_res.json()
    assert data["status"] == "COMPLETED"
    assert data["images_total"] == 2
    assert data["images_processed"] == 2

    # Verify script metadata preservation
    blocks = data["ocr_summary"]["blocks"]
    assert len(blocks) == 12
    latin_blocks = [b for b in blocks if b["image_role"] == "front"]
    dev_blocks = [b for b in blocks if b["image_role"] == "back"]
    assert all(b["detected_script"] == "LATIN" for b in latin_blocks)
    assert all(b["detected_script"] == "DEVANAGARI" for b in dev_blocks)

    # Verify structured product data fusion
    s = data["structured_data"]
    assert s["product_name"] == "Himalayan Pure Honey"
    assert s["common_or_generic_name"] == "Natural Honey"
    assert s["mrp"]["value"] == 250.0
    assert s["mrp"]["includes_taxes"] is True
    assert s["net_quantity"]["value"] == 500.0
    assert s["net_quantity"]["unit"] == "g"
    assert s["unit_sale_price"]["value"] == 0.5
    assert s["dates"]["manufacturing_date"] == "07/2026"
    assert "हिमालयन एग्रो फूड्स" in (s["manufacturer"]["name"] or "")
    assert s["manufacturer"]["pincode"] == "171001"
    assert s["consumer_care"]["phone"] == "1800-444-5555"
    assert s["consumer_care"]["email"] == "care@himalayanagro.in"
    assert s["country_of_origin"] == "India"

    # Verify provenance resolution across both images
    prov = data["provenance"]
    assert prov["product_name"]["source_role"] == "front"
    assert prov["product_name"]["source_image_id"] == front_id
    assert prov["country_of_origin"]["source_role"] == "front"
    assert prov["country_of_origin"]["source_image_id"] == front_id

    assert prov["mrp"]["source_role"] == "back"
    assert prov["mrp"]["source_image_id"] == back_id
    assert prov["net_quantity"]["source_role"] == "back"
    assert prov["net_quantity"]["source_image_id"] == back_id
    assert prov["manufacturer"]["source_role"] == "back"
    assert prov["manufacturer"]["source_image_id"] == back_id
    assert prov["dates"]["source_role"] == "back"
    assert prov["dates"]["source_image_id"] == back_id
    assert prov["consumer_care"]["source_role"] == "back"
    assert prov["consumer_care"]["source_image_id"] == back_id

    # Verify Legal Metrology compliance
    assert data["compliance_status"] == "COMPLIANT"
    assert data["compliance_report"]["rules_passed"] == 8
    assert data["compliance_report"]["rules_failed"] == 0

    # Verify database persistence
    db = SessionLocal()
    try:
        persisted = db.query(Inspection).filter(Inspection.inspection_id == insp_id).first()
        assert persisted is not None
        assert persisted.status == "COMPLETED"
        assert persisted.compliance_status == "COMPLIANT"
        stored_structured = json.loads(persisted.structured_data_json)
        assert stored_structured["mrp"]["value"] == 250.0
        assert stored_structured["net_quantity"]["value"] == 500.0
        assert "हिमालयन एग्रो फूड्स" in stored_structured["manufacturer"]["name"]
        stored_prov = json.loads(persisted.provenance_json)
        assert stored_prov["mrp"]["source_role"] == "back"
        assert stored_prov["country_of_origin"]["source_role"] == "front"
    finally:
        db.close()


def test_14_cross_image_numeric_safety_isolation():
    """14. Cross-image numeric safety: Isolated keyword without digits must not steal numbers from other images."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Safety Isolation Commodity"})
    insp_id = insp_res.json()["inspection_id"]

    img_bytes = make_dummy_image_bytes("png")
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("front.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "front", "sequence": "1"}
    )
    client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("back.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "back", "sequence": "2"}
    )

    ocr_front = make_multilingual_ocr_result([
        ("मूल्य", "DEVANAGARI", 0.95),  # isolated keyword without numeric price
        ("Phone: 9876543210", "LATIN", 0.95),
    ])
    ocr_back = make_multilingual_ocr_result([
        ("शुद्धमात्रा Iड० ग्राम", "MIXED", 0.90),  # corrupted numeral token
        ("Batch No: 8842", "LATIN", 0.95),
    ])

    def side_effect(img):
        if not hasattr(side_effect, "count"):
            side_effect.count = 0
        side_effect.count += 1
        return ocr_front if side_effect.count == 1 else ocr_back

    with patch.object(OCRService, "extract_from_image", side_effect=side_effect):
        proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")

    assert proc_res.status_code == 200
    data = proc_res.json()
    assert data["status"] == "COMPLETED"

    # Numeric safety checks
    s = data["structured_data"]
    # Phone number (9876543210) and batch number (8842) must NOT be assigned to MRP
    assert s["mrp"]["value"] is None
    # Corrupted numeral token must NOT be assigned to net quantity
    assert s["net_quantity"]["value"] is None

    # Compliance report must flag missing declarations
    assert data["compliance_status"] == "NON_COMPLIANT"
    assert data["compliance_report"]["rules_failed"] > 0


def test_15_real_image_pipeline_e2e_api():
    """15. Real image end-to-end API pipeline (sample_product_label.png, without mocking)."""
    assert SAMPLE_IMAGE_PATH.exists()

    insp_res = client.post("/api/v1/inspections", json={"product_name": "Nutri-Crunch Cookies"})
    insp_id = insp_res.json()["inspection_id"]

    with open(SAMPLE_IMAGE_PATH, "rb") as f:
        img_bytes = f.read()

    upload_res = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("sample.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "front"}
    )
    assert upload_res.status_code == 201

    proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")
    assert proc_res.status_code == 200
    data = proc_res.json()

    assert data["status"] == "COMPLETED"
    assert data["compliance_status"] == "COMPLIANT"
    assert data["images_processed"] == 1
    assert data["ocr_summary"]["total_blocks"] > 0
    # Script detected on English label
    assert data["ocr_summary"]["blocks"][0]["detected_script"] in {"LATIN", "UNKNOWN"}
    # Extracted fields
    assert data["structured_data"]["mrp"]["value"] == 55.0
    assert data["structured_data"]["net_quantity"]["value"] == 200.0
    assert data["compliance_report"]["rules_passed"] == 8


def test_16_real_mixed_image_pipeline_e2e_api():
    """16. Real mixed-script image end-to-end API pipeline (without mocking)."""
    from tests.test_ocr import create_synthetic_mixed_image
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Mixed Script Snack"})
    insp_id = insp_res.json()["inspection_id"]

    buf = create_synthetic_mixed_image()
    img_bytes = buf.getvalue()

    upload_res = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("mixed_label.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "label"}
    )
    assert upload_res.status_code == 201

    proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")
    assert proc_res.status_code == 200
    data = proc_res.json()

    assert data["status"] == "COMPLETED"
    assert data["images_processed"] == 1
    assert data["ocr_summary"]["total_blocks"] >= 2

    scripts = {b["detected_script"] for b in data["ocr_summary"]["blocks"]}
    assert "LATIN" in scripts
    assert ("DEVANAGARI" in scripts or "MIXED" in scripts)

    # Structured data extracts MRP and Net Qty
    assert data["structured_data"]["mrp"]["value"] == 120.0
    assert data["structured_data"]["net_quantity"]["value"] == 150.0
    assert data["structured_data"]["net_quantity"]["unit"] == "g"


def test_17_real_devanagari_single_image_e2e_api():
    """17. Real Devanagari image end-to-end API pipeline with synthetic Devanagari image."""
    insp_res = client.post("/api/v1/inspections", json={"product_name": "Devanagari Net Qty Test"})
    insp_id = insp_res.json()["inspection_id"]

    buf = create_synthetic_devanagari_image("शुद्ध मात्रा")
    img_bytes = buf.getvalue()

    upload_res = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("devanagari_label.png", io.BytesIO(img_bytes), "image/png")},
        data={"image_role": "label"}
    )
    assert upload_res.status_code == 201

    proc_res = client.post(f"/api/v1/inspections/{insp_id}/process")
    assert proc_res.status_code == 200
    data = proc_res.json()

    assert data["status"] == "COMPLETED"
    assert data["images_processed"] == 1
    assert data["ocr_summary"]["total_blocks"] >= 1

    dev_blocks = [b for b in data["ocr_summary"]["blocks"] if b["detected_script"] == "DEVANAGARI"]
    assert len(dev_blocks) >= 1
    assert dev_blocks[0]["script_confidence"] == 1.0
    assert "शुद्ध" in (data["structured_data"]["net_quantity"]["raw_text"] or "")

