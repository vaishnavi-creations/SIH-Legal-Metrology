import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from main import app
from app.extractor.gemini_parser import StructuredDataExtractor

client = TestClient(app)

SAMPLE_OCR_TEXT = """
NUTRI-CRUNCH ALMOND COOKIES
Common/Generic Name: Baked Oat Cookies
Net Quantity: 200 g (Unit Sale Price: Rs. 0.275/g)
MRP: Rs. 55.00 (inclusive of all taxes)
Month & Year of Manufacture: 08/2026
Best Before: 6 Months from date of packaging
Manufactured & Packed by: Organic Foods India Pvt Ltd
Factory Address: Plot 42, KIADB Industrial Area, Bengaluru - 560066
Consumer Care: Email: care@nutricrunch.com | Toll Free: 1800-200-1122
Country of Origin: India
Batch No: BATCH-NC-8842
"""

SAMPLE_IMAGE_PATH = Path(__file__).resolve().parent.parent.parent / "samples" / "sample_product_label.png"

@pytest.mark.anyio
async def test_extractor_direct_logic():
    """Verify that StructuredDataExtractor correctly maps raw text into typed fields."""
    result = await StructuredDataExtractor.extract(SAMPLE_OCR_TEXT)

    assert result is not None
    assert result.product_name is not None
    assert "NUTRI-CRUNCH" in result.product_name

    # Check MRP
    assert result.mrp.value == 55.0
    assert result.mrp.includes_taxes is True
    assert result.mrp.currency == "INR"

    # Check Net Quantity
    assert result.net_quantity.value == 200.0
    assert result.net_quantity.unit == "g"

    # Check Dates
    assert result.dates.manufacturing_date == "08/2026"
    assert result.dates.best_before is not None
    assert "6 Months" in result.dates.best_before

    # Check Manufacturer
    assert result.manufacturer.pincode == "560066"
    assert "Organic Foods" in (result.manufacturer.name or "")

    # Check Consumer Care
    assert result.consumer_care.email == "care@nutricrunch.com"
    assert "1800-200-1122" in (result.consumer_care.phone or "")

    # Check Origin & Batch
    assert result.country_of_origin == "India"
    assert result.batch_number == "BATCH-NC-8842"

def test_api_extract_structured_endpoint():
    """Verify POST /api/extract/structured with text payload."""
    payload = {"text": SAMPLE_OCR_TEXT}
    response = client.post("/api/extract/structured", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["mrp"]["value"] == 55.0
    assert data["data"]["net_quantity"]["value"] == 200.0
    assert data["data"]["consumer_care"]["email"] == "care@nutricrunch.com"

def test_api_extract_empty_text():
    """Verify that sending empty text returns 400 Bad Request."""
    payload = {"text": "   "}
    response = client.post("/api/extract/structured", json=payload)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_api_process_all_pipeline():
    """Verify POST /api/scan/process-all runs Preprocess + OCR + Structured Extraction."""
    assert SAMPLE_IMAGE_PATH.exists()
    with open(SAMPLE_IMAGE_PATH, "rb") as f:
        files = {"file": ("sample.png", f, "image/png")}
        response = client.post("/api/scan/process-all", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["file_id"] != ""
    assert data["image_dimensions"]["width"] > 0
    assert data["ocr_result"]["block_count"] > 0
    assert data["structured_data"]["mrp"]["value"] == 55.0
    assert data["structured_data"]["net_quantity"]["value"] == 200.0
    assert data["structured_data"]["consumer_care"]["email"] == "care@nutricrunch.com"

def test_api_extract_by_file_id():
    """Verify uploading an image then extracting structured data by file_id."""
    with open(SAMPLE_IMAGE_PATH, "rb") as f:
        files = {"file": ("sample.png", f, "image/png")}
        upload_res = client.post("/api/scan/upload", files=files)
    assert upload_res.status_code == 201
    file_id = upload_res.json()["file_id"]

    # Extract by file_id
    res = client.post(f"/api/extract/by-file-id/{file_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["file_id"] == file_id
    assert data["data"]["mrp"]["value"] == 55.0


@pytest.mark.anyio
async def test_mrp_multiline_and_unicode_variants():
    """Verify MRP extraction across multiple lines and unicode fullwidth punctuation."""
    test_cases = [
        ("MRP : 50.00\n(inclusive of all taxes)", 50.0),
        ("MRP \uff1a 50.00\n(incl. of all taxes)", 50.0),
        ("MRP\n50.00\ninclusive of all taxes", 50.0),
        ("MRP\n\uff1a\n50.00\n(inclusive of all taxes)", 50.0),
        ("MRP\n\uff1a50.00(Inclusiveofalltaxes)", 50.0),
        ("Maximum Retail Price: Rs. 199.99 (inclusive of all taxes)", 199.99),
        ("M.R.P. : Rs 75\nincl. of all taxes", 75.0),
    ]

    for raw_text, expected_val in test_cases:
        res = await StructuredDataExtractor.extract(raw_text)
        assert res.mrp.value == expected_val, f"Failed for text: {repr(raw_text)}"
        assert res.mrp.includes_taxes is True


@pytest.mark.anyio
async def test_manufacturer_name_extraction_variants():
    """Verify manufacturer name extraction from different keyword patterns."""
    cases = [
        ("Manufacturer: Demo Foods Pvt. Ltd.\nPlot 1, Pune - 410501", "Demo Foods Pvt. Ltd."),
        ("Manufacturer:\nDemo Foods Pvt. Ltd.\nPlot 1, Pune - 410501", "Demo Foods Pvt. Ltd."),
        ("Manufactured & Packed by: Organic Foods India Pvt Ltd\nBengaluru - 560066", "Organic Foods India Pvt Ltd"),
        ("Mfg by: Tasty Snacks Corp.\nMumbai - 400001", "Tasty Snacks Corp."),
    ]

    for raw_text, expected_name in cases:
        res = await StructuredDataExtractor.extract(raw_text)
        assert res.manufacturer.name == expected_name, f"Failed for text: {repr(raw_text)}"


@pytest.mark.anyio
async def test_unit_sale_price_extraction():
    """Verify Unit Sale Price extraction for valid patterns and rejection of false positives."""
    # Positive cases
    pos_cases = [
        ("Net Qty: 200g\nUnit Sale Price: Rs. 0.275/g", 0.275, "g"),
        ("Unit Sale Price :0.50per100g", 0.5, "100g"),
        ("Unit Sale Price\uff1a\u59290.50per100g", 0.5, "100g"),
        ("USP: Rs. 25.00 / kg", 25.0, "kg"),
        ("USP: 0.10 / ml", 0.1, "ml"),
    ]
    for raw_text, expected_val, expected_unit in pos_cases:
        res = await StructuredDataExtractor.extract(raw_text)
        assert res.unit_sale_price is not None, f"Expected USP for: {repr(raw_text)}"
        assert res.unit_sale_price.value == expected_val
        assert res.unit_sale_price.unit == expected_unit

    # Negative cases: prices, MRP, quantities, phone numbers, or dates must NOT match USP
    neg_cases = [
        "Net Quantity: 100g | MRP: Rs 50 | Date: 08/2026 | Phone: 9876543210",
        "MRP: Rs. 50.00 (inclusive of all taxes)",
        "Packed: 08/2026 | Batch No: 12345",
        "Toll Free: 1800-200-1122",
    ]
    for raw_text in neg_cases:
        res = await StructuredDataExtractor.extract(raw_text)
        assert res.unit_sale_price is None, f"Unexpected USP match for: {repr(raw_text)}"


@pytest.mark.anyio
async def test_full_biscuits_sample_extraction():
    """Verify extraction on the exact raw OCR text produced for the biscuits packaging."""
    raw_ocr = """DEMO CRUNCH
BISCUITS
Great Taste, Everyday Happiness
CLASSIC BUTTER BISCUITS
Commodity
\uff1aBiscuits
Net Quantity:100 g
MRP
\uff1a50.00(Inclusiveofalltaxes)
Unit Sale Price\uff1a\u59290.50per100g
Packed
\uff1a08/2026
Manufacturer:Demo Foods Pvt.Ltd.
PlotNo.123,FoodPark,MIDc,
Chakan,Pune-410501
Maharashtra,India
Consumer Care:Forfeedback/complaints,contact
our ConsumerCare Executive at:
Phone:+919876543210
Email:care@demofoods.in
Country of Origin:India"""

    res = await StructuredDataExtractor.extract(raw_ocr)

    # 1. MRP
    assert res.mrp.value == 50.0
    assert res.mrp.includes_taxes is True
    # 2. Manufacturer
    assert res.manufacturer.name == "Demo Foods Pvt.Ltd."
    assert res.manufacturer.pincode == "410501"
    # 3. Unit Sale Price
    assert res.unit_sale_price is not None
    assert res.unit_sale_price.value == 0.5
    assert res.unit_sale_price.unit == "100g"
    # 4. Net quantity & dates
    assert res.net_quantity.value == 100.0
    assert res.dates.manufacturing_date == "08/2026"

