import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from main import app
from app.schemas.product import (
    StructuredProductData,
    MRPDetails,
    NetQuantityDetails,
    DateDetails,
    ManufacturerDetails,
    ConsumerCareDetails
)
from app.rules.engine import rule_engine
from app.rules.models import ComplianceStatus, RuleStatus

client = TestClient(app)
SAMPLE_IMAGE_PATH = Path(__file__).resolve().parent.parent.parent / "samples" / "sample_product_label.png"

def create_compliant_product() -> StructuredProductData:
    """Helper creating a 100% compliant packaged product declaration."""
    return StructuredProductData(
        product_name="Nutri-Crunch Oat Cookies",
        common_or_generic_name="Baked Oat Cookies",
        brand="Nutri-Crunch",
        mrp=MRPDetails(
            raw_text="MRP: Rs. 55.00 (inclusive of all taxes)",
            value=55.0,
            currency="INR",
            includes_taxes=True,
            unit_sale_price="Rs. 0.275/g"
        ),
        net_quantity=NetQuantityDetails(
            raw_text="Net Quantity: 200 g",
            value=200.0,
            unit="g"
        ),
        dates=DateDetails(
            raw_text="Mfg Date: 08/2026",
            manufacturing_date="08/2026",
            best_before="6 Months from date of packaging"
        ),
        manufacturer=ManufacturerDetails(
            raw_text="Manufactured by Organic Foods India Ltd, Bengaluru - 560066",
            name="Organic Foods India Ltd",
            address="Plot 42, KIADB Industrial Area, Bengaluru",
            pincode="560066",
            entity_type="manufacturer"
        ),
        consumer_care=ConsumerCareDetails(
            raw_text="Consumer Care: 1800-200-1122, care@nutricrunch.com",
            phone="1800-200-1122",
            email="care@nutricrunch.com"
        ),
        country_of_origin="India",
        batch_number="BATCH-NC-8842"
    )

# Test 1: Fully compliant sample
def test_fully_compliant_sample():
    prod = create_compliant_product()
    report = rule_engine.evaluate_compliance(prod)
    assert report.compliance_status == ComplianceStatus.COMPLIANT
    assert report.rules_failed == 0
    assert len(report.violations) == 0
    assert report.rules_passed >= 6

# Test 2: Missing MRP
def test_missing_mrp():
    prod = create_compliant_product()
    prod.mrp = MRPDetails()  # Missing MRP value
    report = rule_engine.evaluate_compliance(prod)
    assert report.compliance_status == ComplianceStatus.NON_COMPLIANT
    assert report.rules_failed >= 1
    mrp_violation = next((v for v in report.violations if v.field == "mrp"), None)
    assert mrp_violation is not None
    assert "Rule 6(1)(e)" in mrp_violation.legal_reference

# Test 3: Missing Net Quantity
def test_missing_net_quantity():
    prod = create_compliant_product()
    prod.net_quantity = NetQuantityDetails()  # Missing net quantity
    report = rule_engine.evaluate_compliance(prod)
    assert report.compliance_status == ComplianceStatus.NON_COMPLIANT
    qty_violation = next((v for v in report.violations if v.field == "net_quantity"), None)
    assert qty_violation is not None
    assert "Rule 6(1)(c)" in qty_violation.legal_reference

# Test 4: Missing Manufacturer details
def test_missing_manufacturer():
    prod = create_compliant_product()
    prod.manufacturer = ManufacturerDetails()  # Missing manufacturer
    report = rule_engine.evaluate_compliance(prod)
    assert report.compliance_status == ComplianceStatus.NON_COMPLIANT
    mfg_violation = next((v for v in report.violations if v.field == "manufacturer"), None)
    assert mfg_violation is not None
    assert "Rule 6(1)(a)" in mfg_violation.legal_reference

# Test 5: Imported product missing country of origin
def test_imported_product_missing_country_of_origin():
    prod = create_compliant_product()
    prod.country_of_origin = None
    report = rule_engine.evaluate_compliance(prod, context={"is_imported": True})
    assert report.compliance_status == ComplianceStatus.NON_COMPLIANT
    origin_violation = next((v for v in report.violations if v.field == "country_of_origin"), None)
    assert origin_violation is not None
    assert "Rule 6(10)" in origin_violation.legal_reference

# Test 6: Insufficient OCR data
def test_insufficient_ocr_data():
    empty_prod = StructuredProductData(extraction_method="empty_input")
    report = rule_engine.evaluate_compliance(empty_prod, context={"is_incomplete_scan": True})
    assert report.compliance_status == ComplianceStatus.INSUFFICIENT_DATA
    assert report.rules_insufficient_data > 0
    assert "INSUFFICIENT DATA" in report.summary

# Test 7: Applicable statutory exemption (Rule 26(a) <= 10g)
def test_applicable_exemption_rule_26():
    prod = create_compliant_product()
    # Small 5g sachet
    prod.net_quantity = NetQuantityDetails(value=5.0, unit="g")
    report = rule_engine.evaluate_compliance(prod)
    assert report.compliance_status == ComplianceStatus.COMPLIANT
    assert len(report.exemptions_applied) > 0
    assert "Rule 26(a)" in report.exemptions_applied[0]

# Test 8: Unit Sale Price (USP) scenario
def test_unit_sale_price_scenario():
    # Scenario A: 2 kg package missing USP
    prod = create_compliant_product()
    prod.net_quantity = NetQuantityDetails(value=2.0, unit="kg")
    prod.mrp.unit_sale_price = None  # Missing mandatory USP
    report = rule_engine.evaluate_compliance(prod)
    assert report.compliance_status == ComplianceStatus.NON_COMPLIANT
    usp_violation = next((v for v in report.violations if v.field == "unit_sale_price"), None)
    assert usp_violation is not None
    assert "Rule 6(11)" in usp_violation.legal_reference

    # Scenario B: 2 kg package WITH USP
    prod.mrp.unit_sale_price = "Rs. 110.00/kg"
    report_ok = rule_engine.evaluate_compliance(prod)
    assert report_ok.compliance_status == ComplianceStatus.COMPLIANT

# Test 9: Multiple simultaneous violations
def test_multiple_simultaneous_violations():
    prod = create_compliant_product()
    prod.mrp = MRPDetails()  # Missing MRP
    prod.net_quantity = NetQuantityDetails()  # Missing Net Quantity
    prod.manufacturer = ManufacturerDetails()  # Missing Manufacturer
    report = rule_engine.evaluate_compliance(prod)
    assert report.compliance_status == ComplianceStatus.NON_COMPLIANT
    assert report.rules_failed >= 3
    assert len(report.violations) >= 3

# Test 10: API Endpoint POST /api/compliance/check
def test_api_compliance_check_endpoint():
    prod = create_compliant_product()
    payload = {"data": prod.model_dump()}
    response = client.post("/api/compliance/check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["compliance_status"] == "COMPLIANT"
    assert "checks" in data
    assert len(data["checks"]) > 0

# Test 11: End-to-End API POST /api/compliance/inspect-file
def test_api_inspect_file_endpoint():
    assert SAMPLE_IMAGE_PATH.exists()
    with open(SAMPLE_IMAGE_PATH, "rb") as f:
        files = {"file": ("sample.png", f, "image/png")}
        response = client.post("/api/compliance/inspect-file", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "compliance_report" in data
    assert data["compliance_report"]["compliance_status"] in ["COMPLIANT", "NON_COMPLIANT"]
    assert len(data["compliance_report"]["checks"]) > 0

# Test 12: Regression test for packing_date, inclusive_of_taxes, and structured unit_sale_price
def test_regression_user_mapping_case():
    """Verify that dates.packing_date, mrp.inclusive_of_taxes, and structured unit_sale_price map properly."""
    raw_payload = {
        "data": {
            "product_name": "Nutri-Crunch Cookies",
            "common_or_generic_name": "Cookies",
            "mrp": {
                "value": 55.0,
                "inclusive_of_taxes": True
            },
            "net_quantity": {
                "value": 200.0,
                "unit": "g"
            },
            "dates": {
                "packing_date": "08/2026"
            },
            "manufacturer": {
                "name": "Organic Foods India Ltd",
                "address": "Plot 42, Bengaluru",
                "pincode": "560066"
            },
            "consumer_care": {
                "phone": "1800-200-1122",
                "email": "care@nutricrunch.com"
            },
            "unit_sale_price": {
                "value": 0.50,
                "unit": "100 g"
            },
            "country_of_origin": "India"
        }
    }

    response = client.post("/api/compliance/check", json=raw_payload)
    assert response.status_code == 200
    report = response.json()

    # Verify overall compliance
    assert report["compliance_status"] == "COMPLIANT"
    assert report["rules_failed"] == 0

    # Verify LMR-06-1-D (dates)
    date_check = next((c for c in report["checks"] if c["rule_id"] == "LMR-06-1-D"), None)
    assert date_check is not None
    assert date_check["status"] == "PASS"
    assert date_check["extracted_value"] == "08/2026"

    # Verify LMR-06-1-E (mrp)
    mrp_check = next((c for c in report["checks"] if c["rule_id"] == "LMR-06-1-E"), None)
    assert mrp_check is not None
    assert mrp_check["status"] == "PASS"
    assert "inclusive of all taxes" in mrp_check["extracted_value"].lower()

    # Verify LMR-06-11 (unit sale price)
    usp_check = next((c for c in report["checks"] if c["rule_id"] == "LMR-06-11"), None)
    assert usp_check is not None
    assert usp_check["status"] == "PASS"
    assert "0.50" in str(usp_check["extracted_value"])

