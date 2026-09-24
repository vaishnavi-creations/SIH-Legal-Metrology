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


def test_a_commodity_extraction():
    """TEST A: Commodity extraction maps to common_or_generic_name."""
    raw = "Commodity\n:Rice Crackers"
    res = StructuredDataExtractor._extract_with_heuristics(raw)
    assert res.common_or_generic_name == "Rice Crackers"


def test_b_section_marker_rejection():
    """TEST B: Section markers like '--- FRONT ---' are never used as product_name."""
    raw = """--- FRONT ---
DEMOIMPORTED
SNACK
SEAWEED RICECRACKERS"""
    res = StructuredDataExtractor._extract_with_heuristics(raw)
    assert res.product_name != "--- FRONT ---"
    assert res.product_name == "DEMOIMPORTED"


def test_c_importer_extraction():
    """TEST C: Importer declaration sets entity_type='importer' and extracts multi-line address."""
    raw = """Importer:Demo GlobalFoodsPvt.Ltd.
UnitNo.101,AWing,TradeCentre,
BandraKurlaComplex,Mumbai-400
Maharashtra,India."""
    res = StructuredDataExtractor._extract_with_heuristics(raw)
    assert res.manufacturer.name == "Demo GlobalFoodsPvt.Ltd."
    assert res.manufacturer.entity_type == "importer"
    assert res.manufacturer.address is not None
    assert "UnitNo.101" in res.manufacturer.address
    assert "Maharashtra,India" in res.manufacturer.address


def test_d_imported_date():
    """TEST D: Imported date is extracted into dates.manufacturing_date."""
    raw = "Imported:08/2026"
    res = StructuredDataExtractor._extract_with_heuristics(raw)
    assert res.dates.manufacturing_date == "08/2026"


def test_e_ocr_mrp_inclusive_phrase():
    """TEST E: Tolerates OCR artifacts like '(lnclusiveofalltaxes)' with 'l' instead of 'i'."""
    raw = "MRP\n：120.00(lnclusiveofalltaxes)"
    res = StructuredDataExtractor._extract_with_heuristics(raw)
    assert res.mrp.value == 120.0
    assert res.mrp.includes_taxes is True


def test_f_full_real_ocr_regression_case():
    """TEST F: Full regression test for real imported packaged snack OCR."""
    raw_ocr = """--- FRONT ---
DEMOIMPORTED
SNACK
SEAWEED RICECRACKERS
ORIGINALFLAVOUR
/Crispy
VLight&Tasty
/AuthenticJapanese
Style
Commodity
:Rice Crackers
NetQuantity
：150g
MRP
：120.00(lnclusiveofalltaxes)
Imported
：08/2026
Importer
:Demo GlobalFoodsPvt.Ltd.
UnitNo.101,AWing,TradeCentre,
BandraKurlaComplex,Mumbai-400
Maharashtra,India.
ConsumerCare :Forfeedback/complaints,contact
our ConsumerCareExecutiveat:
Phone:+919987654321
Email:care@demoglobal.in
Countryof Origin:Japan"""

    res = StructuredDataExtractor._extract_with_heuristics(raw_ocr)

    # 1. Commodity / Generic Name
    assert res.common_or_generic_name == "Rice Crackers"

    # 2. Product Name (never provenance marker)
    assert res.product_name != "--- FRONT ---"
    assert res.product_name == "DEMOIMPORTED"

    # 3. Importer Details
    assert res.manufacturer.name == "Demo GlobalFoodsPvt.Ltd."
    assert res.manufacturer.entity_type == "importer"
    assert res.manufacturer.address is not None
    assert "UnitNo.101" in res.manufacturer.address
    assert "TradeCentre" in res.manufacturer.address
    assert "Maharashtra,India" in res.manufacturer.address

    # 4. Imported Date
    assert res.dates.manufacturing_date == "08/2026"

    # 5. MRP & Taxes
    assert res.mrp.value == 120.0
    assert res.mrp.includes_taxes is True

    # 6. Country of Origin
    assert res.country_of_origin == "Japan"

    # 7. Consumer Care
    assert res.consumer_care.email == "care@demoglobal.in"
    assert res.consumer_care.phone == "+919987654321"

    # 8. Net Quantity
    assert res.net_quantity.value == 150.0
    assert res.net_quantity.unit == "g"

    # 9. Unit Sale Price is None (not present in OCR, do not invent)
    assert res.unit_sale_price is None


def test_devanagari_mrp_standard():
    """Test 1: 'अधिकतम खुदरा मूल्य ₹120' -> mrp.value = 120.0"""
    res = StructuredDataExtractor._extract_with_heuristics("अधिकतम खुदरा मूल्य ₹120")
    assert res.mrp.value == 120.0


def test_devanagari_mrp_collapsed_spaces():
    """Test 2: 'अधिकतमखुदरामूल्य 120' -> mrp.value = 120.0"""
    res = StructuredDataExtractor._extract_with_heuristics("अधिकतमखुदरामूल्य 120")
    assert res.mrp.value == 120.0


def test_devanagari_net_quantity_standard():
    """Test 3: 'शुद्ध मात्रा 150 ग्राम' -> net_quantity.value = 150.0, unit = 'g'"""
    res = StructuredDataExtractor._extract_with_heuristics("शुद्ध मात्रा 150 ग्राम")
    assert res.net_quantity.value == 150.0
    assert res.net_quantity.unit == "g"


def test_devanagari_net_quantity_collapsed_spaces():
    """Test 4: 'शुद्धमात्रा 150 ग्राम' -> net_quantity.value = 150.0, unit = 'g'"""
    res = StructuredDataExtractor._extract_with_heuristics("शुद्धमात्रा 150 ग्राम")
    assert res.net_quantity.value == 150.0
    assert res.net_quantity.unit == "g"


def test_devanagari_manufacturer():
    """Test 5: 'निर्माता: स्वादिष्ट फूड्स' -> manufacturer.name contains 'स्वादिष्ट फूड्स', entity_type = 'manufacturer'"""
    res = StructuredDataExtractor._extract_with_heuristics("निर्माता: स्वादिष्ट फूड्स")
    assert "स्वादिष्ट फूड्स" in (res.manufacturer.name or "")
    assert res.manufacturer.entity_type == "manufacturer"


def test_devanagari_consumer_care():
    """Test 6: 'उपभोक्ता देखभाल' -> consumer care recognized"""
    res = StructuredDataExtractor._extract_with_heuristics("उपभोक्ता देखभाल")
    assert res.consumer_care.raw_text is not None
    assert "उपभोक्ता देखभाल" in res.consumer_care.raw_text


def test_devanagari_dates():
    """Test 7: 'निर्माण तिथि: 08/2026' -> dates.manufacturing_date = '08/2026'"""
    res = StructuredDataExtractor._extract_with_heuristics("निर्माण तिथि: 08/2026")
    assert res.dates.manufacturing_date == "08/2026"


def test_mixed_script_mrp():
    """Test 8: 'MRP 120 / अधिकतम खुदरा मूल्य' -> mrp.value = 120.0"""
    res = StructuredDataExtractor._extract_with_heuristics("MRP 120 / अधिकतम खुदरा मूल्य")
    assert res.mrp.value == 120.0


def test_mixed_script_net_quantity():
    """Test 9: 'Net Quantity 150 g / शुद्ध मात्रा' -> net_quantity.value = 150.0, unit = 'g'"""
    res = StructuredDataExtractor._extract_with_heuristics("Net Quantity 150 g / शुद्ध मात्रा")
    assert res.net_quantity.value == 150.0
    assert res.net_quantity.unit == "g"


def test_devanagari_isolated_keyword_rejection():
    """Test 10: 'मूल्य' -> mrp.value is None (no number invented)"""
    res = StructuredDataExtractor._extract_with_heuristics("मूल्य")
    assert res.mrp.value is None


def test_devanagari_corrupted_numeral_rejection():
    """Test 11: 'शुद्धमात्रा Iड० ग्राम' -> net_quantity.value is None (ambiguous token rejected)"""
    res = StructuredDataExtractor._extract_with_heuristics("शुद्धमात्रा Iड० ग्राम")
    assert res.net_quantity.value is None


def test_multilingual_combined_label():
    """Test 12: Combined multilingual label declaration extraction."""
    raw = """--- FRONT ---
स्वादिष्ट बिस्कुट
Common Name: Butter Biscuits
शुद्धमात्रा 150 ग्राम
MRP: ₹120 (सभी करों सहित)
निर्माण तिथि: 08/2026
निर्माता: स्वादिष्ट फूड्स प्रा. लि.
पता: 123 औद्योगिक क्षेत्र, पुणे - 411001
उपभोक्ता देखभाल: 1800-111-2222 | care@swadisht.in
उत्पत्ति का देश: भारत
"""
    res = StructuredDataExtractor._extract_with_heuristics(raw)
    assert res.product_name == "स्वादिष्ट बिस्कुट"
    assert res.common_or_generic_name == "Butter Biscuits"
    assert res.net_quantity.value == 150.0
    assert res.net_quantity.unit == "g"
    assert res.mrp.value == 120.0
    assert res.mrp.includes_taxes is True
    assert res.dates.manufacturing_date == "08/2026"
    assert "स्वादिष्ट फूड्स" in (res.manufacturer.name or "")
    assert res.manufacturer.pincode == "411001"
    assert res.consumer_care.phone == "1800-111-2222"
    assert res.consumer_care.email == "care@swadisht.in"
    assert res.country_of_origin == "भारत"



