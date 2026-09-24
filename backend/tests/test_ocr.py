import io
import pytest
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient
from main import app
from app.ocr.ocr_service import OCRService
from app.ocr.script_detector import ScriptDetector, ScriptType
from app.schemas.ocr import OCRTextBlock
from app.schemas.inspection import InspectionOCRBlock

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


# ==============================================================================
# PHASE 2: SCRIPT DETECTOR UNIT & INTEGRATION TESTS
# ==============================================================================

def test_script_detector_latin_text():
    """1. Latin text classifies as LATIN with confidence 1.0."""
    script, conf = ScriptDetector.detect_script("Rice Crackers")
    assert script == ScriptType.LATIN.value
    assert conf == 1.0


def test_script_detector_devanagari_text():
    """2. Devanagari text classifies as DEVANAGARI with confidence 1.0."""
    script, conf = ScriptDetector.detect_script("अधिकतम खुदरा मूल्य")
    assert script == ScriptType.DEVANAGARI.value
    assert conf == 1.0


def test_script_detector_mixed_text():
    """3. Mixed Latin and Devanagari classifies as MIXED with confidence 1.0."""
    script, conf = ScriptDetector.detect_script("MRP अधिकतम")
    assert script == ScriptType.MIXED.value
    assert conf == 1.0


def test_script_detector_empty_text():
    """4. Empty or whitespace-only text classifies as UNKNOWN with confidence 0.0."""
    script, conf = ScriptDetector.detect_script("")
    assert script == ScriptType.UNKNOWN.value
    assert conf == 0.0

    script_ws, conf_ws = ScriptDetector.detect_script("   \n\t  ")
    assert script_ws == ScriptType.UNKNOWN.value
    assert conf_ws == 0.0


def test_script_detector_numbers_only():
    """5. Numbers-only strings do not falsely trigger LATIN; classify as UNKNOWN."""
    script, conf = ScriptDetector.detect_script("120.00")
    assert script == ScriptType.UNKNOWN.value
    assert conf == 0.0

    script_deva_nums, conf_deva_nums = ScriptDetector.detect_script("१२०.००")
    assert script_deva_nums == ScriptType.UNKNOWN.value
    assert conf_deva_nums == 0.0


def test_script_detector_punctuation_only():
    """6. Punctuation-only strings classify as UNKNOWN with confidence 0.0."""
    script, conf = ScriptDetector.detect_script(":-()")
    assert script == ScriptType.UNKNOWN.value
    assert conf == 0.0

    script_danda, conf_danda = ScriptDetector.detect_script("।॥-–—")
    assert script_danda == ScriptType.UNKNOWN.value
    assert conf_danda == 0.0


def test_script_detector_latin_plus_numbers():
    """7. Latin text combined with numbers classifies as LATIN with confidence 1.0."""
    script, conf = ScriptDetector.detect_script("MRP 120")
    assert script == ScriptType.LATIN.value
    assert conf == 1.0

    script_qty, conf_qty = ScriptDetector.detect_script("150 g")
    assert script_qty == ScriptType.LATIN.value
    assert conf_qty == 1.0


def test_script_detector_devanagari_plus_numbers():
    """8. Devanagari text combined with numbers classifies as DEVANAGARI with confidence 1.0."""
    script, conf = ScriptDetector.detect_script("मूल्य 120")
    assert script == ScriptType.DEVANAGARI.value
    assert conf == 1.0

    script_qty, conf_qty = ScriptDetector.detect_script("150 ग्राम")
    assert script_qty == ScriptType.DEVANAGARI.value
    assert conf_qty == 1.0


def test_ocr_text_block_schema_backward_compatibility():
    """9. Schema backward compatibility: OCRTextBlock & InspectionOCRBlock default cleanly."""
    block = OCRTextBlock(
        text="Sample",
        confidence=0.95,
        polygon=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
        box_2d=[0, 0, 10, 10]
    )
    assert block.detected_script == "LATIN"
    assert block.script_confidence == 1.0

    insp_block = InspectionOCRBlock(
        image_id=1,
        image_role="front",
        sequence=1,
        text="Sample",
        confidence=0.95,
        polygon=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
        box_2d=[0, 0, 10, 10]
    )
    assert insp_block.detected_script == "LATIN"
    assert insp_block.script_confidence == 1.0


def test_ocr_service_populates_script_metadata():
    """10. OCRService populates detected_script and script_confidence on all extracted blocks."""
    assert SAMPLE_IMAGE_PATH.exists()
    result = OCRService.extract_from_image(SAMPLE_IMAGE_PATH)

    assert result.block_count > 0
    for block in result.blocks:
        assert block.detected_script in {"LATIN", "DEVANAGARI", "MIXED", "UNKNOWN"}
        assert 0.0 <= block.script_confidence <= 1.0
        # If block contains Latin letters, it should be LATIN
        if any(('A' <= c <= 'Z' or 'a' <= c <= 'z') for c in block.text):
            assert block.detected_script in {"LATIN", "MIXED"}


# ==============================================================================
# PHASE 2 - STEP 3: DEVANAGARI & MULTILINGUAL RECOGNITION TESTS
# ==============================================================================

def get_devanagari_font(size: int = 36) -> ImageFont.ImageFont:
    """Helper to locate a compatible Devanagari font or fallback."""
    font_candidates = [
        r"C:\Windows\Fonts\Nirmala.ttc",
        r"C:\Windows\Fonts\mangal.ttf",
        r"C:\Windows\Fonts\aparaj.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for p in font_candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def create_synthetic_devanagari_image(text: str = "शुद्ध मात्रा") -> io.BytesIO:
    """Helper to render synthetic Devanagari text on an image."""
    img = Image.new("RGB", (500, 120), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = get_devanagari_font(36)
    draw.text((30, 35), text, font=font, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def create_synthetic_mixed_image() -> io.BytesIO:
    """Helper to render multi-line image with English and Devanagari packaging text."""
    img = Image.new("RGB", (600, 240), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_dev = get_devanagari_font(32)
    font_en = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 32) if Path(r"C:\Windows\Fonts\arial.ttf").exists() else font_dev

    draw.text((20, 20), "Rice Crackers 150g", font=font_en, fill=(0, 0, 0))
    draw.text((20, 90), "शुद्ध मात्रा १५० ग्राम", font=font_dev, fill=(0, 0, 0))
    draw.text((20, 160), "MRP Rs. 120 / अधिकतम खुदरा मूल्य", font=font_dev, fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_ocr_devanagari_recognition():
    """Verify Devanagari OCR recognition on an image with Devanagari packaging text."""
    import cv2
    import numpy as np

    buf = create_synthetic_devanagari_image("शुद्ध मात्रा")
    img_np = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)

    result = OCRService.extract_from_image(img_np)

    assert result.block_count >= 1
    assert result.average_confidence > 0.5
    devanagari_blocks = [b for b in result.blocks if b.detected_script == "DEVANAGARI"]
    assert len(devanagari_blocks) >= 1
    assert devanagari_blocks[0].script_confidence == 1.0
    assert len(devanagari_blocks[0].box_2d) == 4
    assert len(devanagari_blocks[0].polygon) == 4


def test_ocr_mixed_script_recognition():
    """Verify mixed English + Devanagari recognition preserves both scripts on packaging."""
    import cv2
    import numpy as np

    buf = create_synthetic_mixed_image()
    img_np = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)

    result = OCRService.extract_from_image(img_np)

    assert result.block_count >= 2
    scripts = {b.detected_script for b in result.blocks}
    # Must detect both Latin/English and Devanagari (or Mixed) content
    assert "LATIN" in scripts
    assert ("DEVANAGARI" in scripts or "MIXED" in scripts)
    for b in result.blocks:
        assert b.confidence >= 0.5
        assert len(b.box_2d) == 4


def test_api_process_ocr_devanagari_endpoint():
    """Verify API endpoint POST /api/scan/process-ocr works with Devanagari packaging."""
    buf = create_synthetic_devanagari_image("शुद्ध मात्रा")
    files = {"file": ("hindi_package.png", buf, "image/png")}
    response = client.post("/api/scan/process-ocr", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["ocr_result"]["block_count"] >= 1
    blocks = data["ocr_result"]["blocks"]
    deva_blocks = [b for b in blocks if b["detected_script"] == "DEVANAGARI"]
    assert len(deva_blocks) >= 1
    assert deva_blocks[0]["script_confidence"] == 1.0


