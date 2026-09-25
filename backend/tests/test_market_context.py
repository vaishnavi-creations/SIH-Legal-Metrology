import pytest
from app.db.models import Inspection
from app.schemas.product import (
    StructuredProductData,
    ManufacturerDetails,
    NetQuantityDetails,
    MRPDetails
)
from app.rules.engine import rule_engine
from app.rules.models import RuleStatus, ComplianceStatus
from app.ocr.parser import detect_statutory_physical_signals, normalize_market_channel
from app.inspection.processor import (
    build_context_provenance,
    normalize_country_name,
    is_india_country,
    is_foreign_country
)


def test_1_country_context_propagation():
    """1. Verify country_of_manufacture and country_of_sale reach the execution context."""
    insp = Inspection(
        inspection_id="test-prop-001",
        is_imported=True,
        commodity_type="Confectionery",
        country_of_manufacture="Germany",
        country_of_sale="India"
    )
    structured = StructuredProductData(
        product_name="German Chocolate",
        country_of_origin="Germany"
    )

    prov = build_context_provenance(insp, structured)
    context = {
        "is_imported": insp.is_imported,
        "commodity_type": insp.commodity_type or "",
        "country_of_manufacture": insp.country_of_manufacture,
        "country_of_sale": insp.country_of_sale,
        "context_provenance": prov
    }

    assert context["country_of_manufacture"] == "Germany"
    assert context["country_of_sale"] == "India"
    assert context["is_imported"] is True
    assert context["commodity_type"] == "Confectionery"
    assert context["context_provenance"]["explicit"]["country_of_manufacture"] == "Germany"
    assert context["context_provenance"]["explicit"]["country_of_sale"] == "India"


def test_2_explicit_import_flag_preserved():
    """2. Verify explicit is_imported flag is strictly preserved as True or False without mutation."""
    # Case A: Explicitly True
    insp_true = Inspection(
        inspection_id="test-flag-true",
        is_imported=True,
        country_of_manufacture="Japan"
    )
    prov_true = build_context_provenance(insp_true, StructuredProductData())
    assert insp_true.is_imported is True
    assert prov_true["explicit"]["is_imported"] is True

    # Case B: Explicitly False
    insp_false = Inspection(
        inspection_id="test-flag-false",
        is_imported=False,
        country_of_manufacture="India"
    )
    prov_false = build_context_provenance(insp_false, StructuredProductData())
    assert insp_false.is_imported is False
    assert prov_false["explicit"]["is_imported"] is False


def test_3_country_context_provenance():
    """3. Verify explicit country fields, extracted origin, and derived status are represented cleanly."""
    insp = Inspection(
        inspection_id="test-prov-003",
        is_imported=True,
        commodity_type="Electronics",
        country_of_manufacture="South Korea",
        country_of_sale="India"
    )
    structured = StructuredProductData(
        country_of_origin="South Korea",
        manufacturer=ManufacturerDetails(
            name="Seoul Tech Co.",
            entity_type="importer"
        )
    )

    prov = build_context_provenance(insp, structured)

    # Explicit
    assert prov["explicit"]["country_of_manufacture"] == "South Korea"
    assert prov["explicit"]["country_of_sale"] == "India"
    assert prov["explicit"]["is_imported"] is True
    assert prov["explicit"]["commodity_type"] == "Electronics"

    # Extracted
    assert prov["extracted"]["country_of_origin"] == "South Korea"
    assert prov["extracted"]["entity_type"] == "importer"

    # Derived
    assert prov["derived"]["manufacture_is_foreign"] is True
    assert prov["derived"]["manufacture_is_india"] is False
    assert prov["derived"]["origin_is_foreign"] is True
    assert prov["derived"]["origin_is_india"] is False

    # No contradictions
    assert len(prov["conflicts"]) == 0


def test_4_import_context_conflict_detection():
    """4. Verify explicit imported=False + clearly foreign manufacture produces a context conflict without altering compliance."""
    insp = Inspection(
        inspection_id="test-conflict-foreign",
        is_imported=False,  # Contradicts German manufacture
        country_of_manufacture="Germany",
        country_of_sale="India"
    )
    structured = StructuredProductData(
        product_name="Imported Wafer",
        country_of_origin="Germany"
    )

    prov = build_context_provenance(insp, structured)
    conflicts = prov["conflicts"]

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict["field"] == "is_imported"
    assert conflict["conflict_type"] == "IMPORT_STATUS_CONTRADICTION"
    assert conflict["explicit_value"] is False
    assert conflict["competing_value"] == "Germany"

    # Verify that existing Rule 6(10) decision remains unchanged by conflict presence
    # (Country of origin is declared as Germany, so Rule 6(10) evaluates and PASSES)
    context = {
        "is_imported": insp.is_imported,
        "commodity_type": insp.commodity_type or "",
        "country_of_manufacture": insp.country_of_manufacture,
        "country_of_sale": insp.country_of_sale,
        "context_provenance": prov
    }
    report = rule_engine.evaluate_compliance(structured, context=context)
    rule_6_10 = next(c for c in report.checks if c.rule_id == "LMR-06-10")
    assert rule_6_10.status == RuleStatus.PASS


def test_5_import_context_conflict_reverse():
    """5. Verify explicit imported=True + clearly Indian manufacture produces a context conflict without altering Rule 6(10)."""
    insp = Inspection(
        inspection_id="test-conflict-domestic",
        is_imported=True,  # Contradicts Indian manufacture
        country_of_manufacture="India",
        country_of_sale="India"
    )
    structured = StructuredProductData(
        product_name="Domestic Ghee",
        country_of_origin="India"
    )

    prov = build_context_provenance(insp, structured)
    conflicts = prov["conflicts"]

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict["field"] == "is_imported"
    assert conflict["conflict_type"] == "IMPORT_STATUS_CONTRADICTION"
    assert conflict["explicit_value"] is True
    assert conflict["competing_value"] == "India"

    # Verify Rule 6(10) semantics remain authoritative on is_imported and declared origin
    context = {
        "is_imported": insp.is_imported,
        "commodity_type": insp.commodity_type or "",
        "country_of_manufacture": insp.country_of_manufacture,
        "country_of_sale": insp.country_of_sale,
        "context_provenance": prov
    }
    report = rule_engine.evaluate_compliance(structured, context=context)
    rule_6_10 = next(c for c in report.checks if c.rule_id == "LMR-06-10")
    assert rule_6_10.status == RuleStatus.PASS
    assert rule_6_10.extracted_value == "India"


def test_6_missing_country_context():
    """6. Verify missing country fields remain absent/None rather than being silently fabricated."""
    insp = Inspection(
        inspection_id="test-missing-country",
        is_imported=False,
        commodity_type=None,
        country_of_manufacture=None,
        country_of_sale=None
    )
    structured = StructuredProductData()

    prov = build_context_provenance(insp, structured)
    assert prov["explicit"]["country_of_manufacture"] is None
    assert prov["explicit"]["country_of_sale"] is None
    assert prov["explicit"]["commodity_type"] is None
    assert prov["extracted"]["country_of_origin"] is None
    assert prov["extracted"]["entity_type"] == "manufacturer_or_packer"
    assert len(prov["conflicts"]) == 0


def test_7_rule_6_10_regression():
    """7. Verify existing Rule 6(10) behavior remains completely unchanged."""
    # Case A: Domestic product (is_imported=False), no origin declared -> NOT_APPLICABLE
    domestic_data = StructuredProductData(product_name="Local Bread")
    report_dom = rule_engine.evaluate_compliance(domestic_data, context={"is_imported": False})
    check_dom = next(c for c in report_dom.checks if c.rule_id == "LMR-06-10")
    assert check_dom.status == RuleStatus.NOT_APPLICABLE

    # Case B: Imported product (is_imported=True), no origin declared -> FAIL
    report_imp_fail = rule_engine.evaluate_compliance(domestic_data, context={"is_imported": True})
    check_imp_fail = next(c for c in report_imp_fail.checks if c.rule_id == "LMR-06-10")
    assert check_imp_fail.status == RuleStatus.FAIL

    # Case C: Imported product (is_imported=True), origin declared -> PASS
    imported_data = StructuredProductData(
        product_name="Swiss Chocolate",
        country_of_origin="Switzerland"
    )
    report_imp_pass = rule_engine.evaluate_compliance(imported_data, context={"is_imported": True})
    check_imp_pass = next(c for c in report_imp_pass.checks if c.rule_id == "LMR-06-10")
    assert check_imp_pass.status == RuleStatus.PASS


def test_8_missing_market_channel_backward_compatible():
    """8. Verify missing market_channel remains fully backward compatible and defaults to Chapter II retail evaluation."""
    insp = Inspection(
        inspection_id="test-chan-missing",
        is_imported=False,
        commodity_type="Biscuits",
        country_of_sale="India"
    )
    structured = StructuredProductData(product_name="Glucose Biscuit")

    prov = build_context_provenance(insp, structured)

    assert prov["market_context"]["claimed_channel"] is None
    assert prov["market_context"]["normalized_channel"] == "UNKNOWN"
    assert prov["statutory_determination"]["chapter_ii_applicable"] is True
    assert prov["statutory_determination"]["applicable_chapter"] == "CHAPTER_II"

    # Rule evaluation functions under standard Chapter II baseline
    context = {"context_provenance": prov, "is_imported": False}
    report = rule_engine.evaluate_compliance(structured, context=context)
    assert report.rules_checked == 8


def test_9_retail_channel_normal_chapter_ii():
    """9. Verify RETAIL channel produces normal Chapter II evaluation behavior."""
    insp = Inspection(
        inspection_id="test-chan-retail",
        is_imported=False,
        country_of_sale="India"
    )
    structured = StructuredProductData(product_name="Retail Soap")

    prov = build_context_provenance(insp, structured, market_channel="RETAIL")

    assert prov["market_context"]["claimed_channel"] == "RETAIL"
    assert prov["market_context"]["normalized_channel"] == "RETAIL"
    assert prov["statutory_determination"]["chapter_ii_applicable"] is True
    assert prov["statutory_determination"]["statutory_basis"] == "Rule 3 (Standard Domestic Retail)"
    assert prov["statutory_determination"]["determination_status"] == "DETERMINED"


def test_10_unknown_channel_provenance_and_scrutiny():
    """10. Verify UNKNOWN remains UNKNOWN in provenance while Chapter II scrutiny is retained."""
    insp = Inspection(
        inspection_id="test-chan-unknown",
        is_imported=False
    )
    structured = StructuredProductData(product_name="Unknown Channel Product")

    prov = build_context_provenance(insp, structured, market_channel="UNKNOWN")

    # Does NOT write RETAIL as claimed channel
    assert prov["market_context"]["claimed_channel"] == "UNKNOWN"
    assert prov["market_context"]["normalized_channel"] == "UNKNOWN"
    assert prov["statutory_determination"]["chapter_ii_applicable"] is True
    assert prov["statutory_determination"]["statutory_basis"] == "Special market-context exemption not established."


def test_11_institutional_with_not_for_retail_sale_not_applicable():
    """11. Verify INSTITUTIONAL + 'Not for retail sale' renders Chapter II NOT_APPLICABLE under Rule 3(b)."""
    insp = Inspection(
        inspection_id="test-chan-inst-corroborated",
        is_imported=False
    )
    structured = StructuredProductData(product_name="Hotel Shampoo 5L")
    ocr_text = "Bulk Pack for Hotel. NOT FOR RETAIL SALE. Manufactured by ABC Ltd."

    prov = build_context_provenance(
        insp,
        structured,
        ocr_text=ocr_text,
        market_channel="INSTITUTIONAL"
    )

    assert prov["physical_signals"]["not_for_retail_sale_detected"] is True
    assert prov["statutory_determination"]["chapter_ii_applicable"] is False
    assert prov["statutory_determination"]["statutory_basis"] == "Rule 3(b) read with Rule 2(bc)"
    assert prov["statutory_determination"]["determination_status"] == "NOT_APPLICABLE"
    # Diagnostic boundary recorded: commercial context not verified from package images alone
    assert prov["diagnostics"]["commercial_context_verified"] is False

    # Compliance report evaluates to NOT_APPLICABLE for all Chapter II checks
    context = {
        "context_provenance": prov,
        "chapter_ii_applicable": False,
        "is_imported": False
    }
    report = rule_engine.evaluate_compliance(structured, context=context)
    assert report.compliance_status == ComplianceStatus.NOT_APPLICABLE
    assert report.rules_not_applicable == 8
    assert all(c.status == RuleStatus.NOT_APPLICABLE for c in report.checks)
    assert "Rule 3(b)" in report.summary


def test_12_industrial_with_physical_marking_not_applicable():
    """12. Verify INDUSTRIAL + 'For industrial use only' renders Chapter II NOT_APPLICABLE under Rule 3(b)."""
    insp = Inspection(
        inspection_id="test-chan-ind-corroborated",
        is_imported=False
    )
    structured = StructuredProductData(product_name="Industrial Resin 50kg")
    ocr_text = "Grade 404 Chemical. FOR INDUSTRIAL USE ONLY. Chemical Works Pvt Ltd."

    prov = build_context_provenance(
        insp,
        structured,
        ocr_text=ocr_text,
        market_channel="INDUSTRIAL"
    )

    assert prov["physical_signals"]["for_industrial_use_only_detected"] is True
    assert prov["statutory_determination"]["chapter_ii_applicable"] is False
    assert prov["statutory_determination"]["statutory_basis"] == "Rule 3(b) read with Rule 2(bb)"
    assert prov["statutory_determination"]["determination_status"] == "NOT_APPLICABLE"
    assert prov["diagnostics"]["commercial_context_verified"] is False

    context = {
        "context_provenance": prov,
        "chapter_ii_applicable": False,
        "is_imported": False
    }
    report = rule_engine.evaluate_compliance(structured, context=context)
    assert report.compliance_status == ComplianceStatus.NOT_APPLICABLE
    assert report.rules_not_applicable == 8


def test_13_institutional_without_marking_uncorroborated():
    """13. Verify INSTITUTIONAL claim without 'not for retail sale' leaves Chapter II applicable and emits diagnostic."""
    insp = Inspection(
        inspection_id="test-chan-inst-uncorroborated",
        is_imported=False
    )
    structured = StructuredProductData(product_name="Biscuits Claimed Institutional")
    ocr_text = "Delicious Biscuits. Net Qty: 500g. Standard Consumer Pack."

    prov = build_context_provenance(
        insp,
        structured,
        ocr_text=ocr_text,
        market_channel="INSTITUTIONAL"
    )

    assert prov["physical_signals"]["not_for_retail_sale_detected"] is False
    assert prov["statutory_determination"]["chapter_ii_applicable"] is True
    assert prov["statutory_determination"]["determination_status"] == "ENFORCED"

    # Emits diagnostic conflict
    conflict = next(c for c in prov["conflicts"] if c["conflict_type"] == "UNCORROBORATED_INSTITUTIONAL_CLAIM")
    assert conflict["field"] == "market_channel"
    assert "Rule 2(bc)" in conflict["message"]

    # Fails retail compliance because MRP is missing on this claimed package
    context = {"context_provenance": prov, "is_imported": False}
    report = rule_engine.evaluate_compliance(structured, context=context)
    assert report.compliance_status == ComplianceStatus.NON_COMPLIANT
    mrp_check = next(c for c in report.checks if c.rule_id == "LMR-06-1-E")
    assert mrp_check.status == RuleStatus.FAIL


def test_14_industrial_without_marking_uncorroborated():
    """14. Verify INDUSTRIAL claim without physical marking leaves Chapter II applicable and emits diagnostic."""
    insp = Inspection(
        inspection_id="test-chan-ind-uncorroborated",
        is_imported=False
    )
    structured = StructuredProductData(product_name="Bolts and Fasteners")
    ocr_text = "Fasteners. 100 units. Packaged for general trade."

    prov = build_context_provenance(
        insp,
        structured,
        ocr_text=ocr_text,
        market_channel="INDUSTRIAL"
    )

    assert prov["physical_signals"]["for_industrial_use_only_detected"] is False
    assert prov["physical_signals"]["not_for_retail_sale_detected"] is False
    assert prov["statutory_determination"]["chapter_ii_applicable"] is True

    conflict = next(c for c in prov["conflicts"] if c["conflict_type"] == "UNCORROBORATED_INDUSTRIAL_CLAIM")
    assert conflict["field"] == "market_channel"
    assert "Rule 2(bb)" in conflict["message"]


def test_15_ecommerce_channel_no_exemption():
    """15. Verify ECOMMERCE channel creates NO physical packaging exemption and records digital listing boundary."""
    insp = Inspection(
        inspection_id="test-chan-ecommerce",
        is_imported=False
    )
    structured = StructuredProductData(product_name="Online Order Pack")

    prov = build_context_provenance(insp, structured, market_channel="ECOMMERCE")

    assert prov["statutory_determination"]["chapter_ii_applicable"] is True
    assert prov["statutory_determination"]["statutory_basis"] == "Rule 3 & Rule 6(1) (E-commerce physical packages require full Chapter II compliance)"
    # Boundary note recorded: digital platform obligations cannot be certified from package images
    assert prov["diagnostics"]["digital_listing_verified"] is False


def test_16_export_with_marking_unverified_transit():
    """16. Verify EXPORT claim with marking records evidence and maintains unverified transit boundary."""
    insp = Inspection(
        inspection_id="test-chan-export-marked",
        is_imported=False,
        country_of_sale="United Kingdom"
    )
    structured = StructuredProductData(product_name="Export Tea")
    ocr_text = "Assam Premium Tea. FOR EXPORT ONLY. London Consignment."

    prov = build_context_provenance(
        insp,
        structured,
        ocr_text=ocr_text,
        market_channel="EXPORT"
    )

    assert prov["physical_signals"]["for_export_only_detected"] is True
    assert prov["diagnostics"]["customs_export_transit_verified"] is False
    assert "Rule 25" in prov["statutory_determination"]["statutory_basis"]
    assert prov["statutory_determination"]["determination_status"] == "REQUIRES_REVIEW"


def test_17_export_with_contradictory_domestic_sale():
    """17. Verify EXPORT claim with country_of_sale India triggers REQUIRES_REVIEW and conflict."""
    insp = Inspection(
        inspection_id="test-chan-export-domestic-conflict",
        is_imported=False,
        country_of_sale="India"  # Contradicts export claim
    )
    structured = StructuredProductData(product_name="Diverted Coffee")
    ocr_text = "Coffee. For export only."

    prov = build_context_provenance(
        insp,
        structured,
        ocr_text=ocr_text,
        market_channel="EXPORT"
    )

    assert prov["statutory_determination"]["determination_status"] == "REQUIRES_REVIEW"
    assert prov["statutory_determination"]["chapter_ii_applicable"] is True

    conflict = next(c for c in prov["conflicts"] if c["conflict_type"] == "EXPORT_DOMESTIC_TARGET_CONFLICT")
    assert conflict["field"] == "market_channel"
    assert conflict["explicit_value"] == "EXPORT"


def test_18_generic_phrases_not_treated_as_statutory_markings():
    """18. Verify generic non-statutory terms (e.g. 'institutional pack') do NOT satisfy statutory signals."""
    generic_text = "Quality Product. Special institutional pack. Also industrial pack and export pack."
    signals = detect_statutory_physical_signals(generic_text)

    assert signals["not_for_retail_sale_detected"] is False
    assert signals["for_industrial_use_only_detected"] is False
    assert signals["for_export_only_detected"] is False


def test_19_rule_26_a_small_quantity_exemption_preserved():
    """19. Verify existing Rule 26(a) small quantity exemption (<=10g) remains fully functional."""
    small_product = StructuredProductData(
        product_name="Small Sachet",
        net_quantity=NetQuantityDetails(value=5.0, unit="g")
    )
    report = rule_engine.evaluate_compliance(small_product, context={"commodity_type": "Sugar"})
    assert any("Rule 26(a)" in ex for ex in report.exemptions_applied)

