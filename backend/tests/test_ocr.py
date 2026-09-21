import io
import pytest
from pathlib import Path
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from main import app
from app.ocr.ocr_service import OCRService

client = TestClient(app)

SAMPLE_IMAGE_PATH = Path(__file__).resolve().parent.parent.parent / "samples" / "sample_product_label.png"

def create_synthetic_text_image(text: str = "MRP Rs. 99.00 (incl. of all taxes)") -> io.BytesIO:
    """Helper to generate a small image with readable text."""
    img = Image.new("RGB", (500, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 35), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def test_ocr_service_on_sample_label():
    """Verify that OCRService correctly extracts text blocks and coordinates from the sample label."""
    assert SAMPLE_IMAGE_PATH.exists(), f"Sample image not found at {SAMPLE_IMAGE_PATH}"
    result = OCRService.extract_from_image(SAMPLE_IMAGE_PATH)

    assert result.block_count > 0
    assert result.average_confidence > 0.5
    assert len(result.blocks) == result.block_count
    assert "MRP" in result.full_text or "Rs." in result.full_text
    assert result.execution_time_seconds > 0

    # Verify bounding boxes format
    first_block = result.blocks[0]
    assert len(first_block.polygon) == 4
    assert len(first_block.box_2d) == 4
    x_min, y_min, x_max, y_max = first_block.box_2d
    assert x_max >= x_min
    assert y_max >= y_min

def test_ocr_service_blank_image():
    """Verify that a completely blank image returns empty results gracefully without crashing."""
    blank = Image.new("RGB", (300, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    blank.save(buf, format="PNG")
    buf.seek(0)

    import cv2
    import numpy as np
    img_np = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    result = OCRService.extract_from_image(img_np)

    assert result.block_count == 0
    assert result.full_text == ""
    assert result.average_confidence == 0.0

def test_api_process_ocr_endpoint():
    """Verify the end-to-end POST /api/scan/process-ocr endpoint."""
    buf = create_synthetic_text_image("Net Quantity: 500 g")
    files = {"file": ("test_package.png", buf, "image/png")}
    response = client.post("/api/scan/process-ocr", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["file_id"] != ""
    assert data["ocr_result"]["block_count"] >= 1
    assert "500" in data["ocr_result"]["full_text"] or "Net" in data["ocr_result"]["full_text"]

def test_api_ocr_by_file_id():
    """Verify that uploading an image and then calling GET /api/scan/ocr/{file_id} succeeds."""
    buf = create_synthetic_text_image("Customer Care: support@brand.com")
    files = {"file": ("support.png", buf, "image/png")}
    upload_res = client.post("/api/scan/upload", files=files)
    assert upload_res.status_code == 201
    file_id = upload_res.json()["file_id"]

    # Now request OCR extraction for that file_id
    ocr_res = client.get(f"/api/scan/ocr/{file_id}")
    assert ocr_res.status_code == 200
    data = ocr_res.json()
    assert data["success"] is True
    assert data["file_id"] == file_id
    assert data["ocr_result"]["block_count"] >= 1

def test_api_ocr_by_file_id_not_found():
    """Verify that requesting OCR on a non-existent file_id returns 404."""
    response = client.get("/api/scan/ocr/non-existent-uuid-12345")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
