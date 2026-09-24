import pytest
from app.inspection.fusion import (
    normalize_mrp,
    normalize_quantity,
    normalize_unit_sale_price,
    normalize_date,
    normalize_text,
    values_equivalent,
    is_text_enrichment,
    EvidenceCandidate,
    EvidenceFusionResult,
    EvidenceFusionEngine
)
from app.schemas.product import (
    MRPDetails,
    NetQuantityDetails,
    DateDetails,
    UnitSalePriceDetails,
    ManufacturerDetails
)


# ==============================================================================
# 1. MRP Normalization & Equivalence Tests
# ==============================================================================

def test_mrp_normalization_currency_wrappers():
    """Verify that various currency wrappers (₹, Rs, Rs.) and raw numbers normalize to the same float."""
    assert normalize_mrp("₹250") == 250.0
    assert normalize_mrp("Rs. 250") == 250.0
    assert normalize_mrp("Rs 250") == 250.0
    assert normalize_mrp("250") == 250.0
    assert normalize_mrp("₹ 250.00") == 250.0
    assert normalize_mrp("Rs. 250.00 (incl of all taxes)") == 250.0


def test_mrp_normalization_devanagari_numerals():
    """Verify that Devanagari numerals normalize to the same ASCII float value."""
    assert normalize_mrp("२५०") == 250.0
    assert normalize_mrp("₹ २५०.००") == 250.0
    assert normalize_mrp("अधिकतम खुदरा मूल्य २५०") == 250.0


def test_mrp_equivalence():
    """Verify values_equivalent for equivalent and competing MRP declarations."""
    assert values_equivalent("₹250", "Rs. 250", field_type="mrp") is True
    assert values_equivalent("Rs 250", "२५०", field_type="mrp") is True
    assert values_equivalent("₹250", 250.0, field_type="mrp") is True
    assert values_equivalent(MRPDetails(value=250.0), "Rs. 250", field_type="mrp") is True

    # Contradictory prices must NOT be equivalent
    assert values_equivalent(250, 280, field_type="mrp") is False
    assert values_equivalent("₹250", "₹280", field_type="mrp") is False


# ==============================================================================
# 2. Net Quantity Normalization & Equivalence Tests
# ==============================================================================

def test_quantity_normalization_metric_mass():
    """Verify that metric mass units (g, kg) normalize to base grams."""
    assert normalize_quantity("500 g") == (500.0, "g")
    assert normalize_quantity("0.5 kg") == (500.0, "g")
    assert normalize_quantity("1 kg") == (1000.0, "g")
    assert normalize_quantity("1000 g") == (1000.0, "g")


def test_quantity_normalization_hindi_units():
    """Verify that Hindi metric units (ग्राम, किग्रा) normalize to base grams."""
    assert normalize_quantity("500 ग्राम") == (500.0, "g")
    assert normalize_quantity("0.5 किग्रा") == (500.0, "g")
    assert normalize_quantity("५०० ग्राम") == (500.0, "g")


def test_quantity_normalization_volume():
    """Verify that volume units normalize to base milliliters."""
    assert normalize_quantity("500 ml") == (500.0, "ml")
    assert normalize_quantity("0.5 l") == (500.0, "ml")
    assert normalize_quantity("1 litre") == (1000.0, "ml")
    assert normalize_quantity("1 लीटर") == (1000.0, "ml")


def test_quantity_counts_never_converted_to_metric():
    """Verify that pieces and counts remain count-based and are NEVER converted to grams or ml."""
    assert normalize_quantity("10 pieces") == (10.0, "pcs")
    assert normalize_quantity("10 नग") == (10.0, "pcs")
    assert normalize_quantity("10 units") == (10.0, "pcs")

    # Counts must be equivalent to counts, but never equivalent to mass/volume
    assert values_equivalent("10 pieces", "10 नग", field_type="net_quantity") is True
    assert values_equivalent("10 pieces", "10 g", field_type="net_quantity") is False
    assert values_equivalent("10 pieces", "10 ml", field_type="net_quantity") is False


def test_quantity_equivalence():
    """Verify cross-unit and cross-language quantity equivalence."""
    assert values_equivalent("500 g", "0.5 kg", field_type="net_quantity") is True
    assert values_equivalent("500 ग्राम", "500 g", field_type="net_quantity") is True
    assert values_equivalent("1 kg", "1000 g", field_type="net_quantity") is True
    assert values_equivalent("1 किग्रा", "1000 ग्राम", field_type="net_quantity") is True
    assert values_equivalent(
        NetQuantityDetails(value=500.0, unit="g"),
        "0.5 kg",
        field_type="net_quantity"
    ) is True

    # Differing quantities must NOT be equivalent
    assert values_equivalent("200 g", "500 g", field_type="net_quantity") is False
    assert values_equivalent("1 kg", "2 kg", field_type="net_quantity") is False


# ==============================================================================
# 3. Unit Sale Price Normalization Tests
# ==============================================================================

def test_unit_sale_price_normalization():
    """Verify that equivalent unit sale prices across English and Hindi normalize canonically."""
    usp1 = normalize_unit_sale_price("₹0.50 / g")
    usp2 = normalize_unit_sale_price("Rs. 0.50/g")
    usp3 = normalize_unit_sale_price("0.50 प्रति ग्राम")
    usp4 = normalize_unit_sale_price("0.50 / ग्राम")

    assert usp1 == (0.5, "g")
    assert usp2 == (0.5, "g")
    assert usp3 == (0.5, "g")
    assert usp4 == (0.5, "g")


def test_unit_sale_price_equivalence():
    """Verify that English and Hindi USP statements evaluate as equivalent."""
    assert values_equivalent("₹0.50 / g", "Rs. 0.50/g", field_type="unit_sale_price") is True
    assert values_equivalent("0.50 प्रति ग्राम", "0.50 / ग्राम", field_type="unit_sale_price") is True
    assert values_equivalent("Rs. 0.50/g", "0.50 प्रति ग्राम", field_type="unit_sale_price") is True
    assert values_equivalent(
        UnitSalePriceDetails(value=0.5, unit="g"),
        "0.50 / ग्राम",
        field_type="unit_sale_price"
    ) is True

    # Per-kg price is converted to per-g price (Rs 500 / kg = Rs 0.5 / g)
    assert values_equivalent("Rs. 500 / kg", "Rs. 0.50 / g", field_type="unit_sale_price") is True

    # Differing USPs must not be equivalent
    assert values_equivalent("Rs. 0.50 / g", "Rs. 0.80 / g", field_type="unit_sale_price") is False


# ==============================================================================
# 4. Date Normalization Tests
# ==============================================================================

def test_date_normalization_separators():
    """Verify standard date separator variations (slash vs hyphen) normalize identically."""
    assert normalize_date("08/2026") == "08/2026"
    assert normalize_date("08-2026") == "08/2026"
    assert values_equivalent("08/2026", "08-2026", field_type="date") is True


def test_date_normalization_month_names():
    """Verify written month names normalize to standard numerical month representations."""
    assert normalize_date("August 2026") == "08/2026"
    assert normalize_date("Aug 2026") == "08/2026"
    assert values_equivalent("August 2026", "08/2026", field_type="date") is True
    assert values_equivalent("Aug 2026", "08-2026", field_type="date") is True


def test_date_normalization_full_dates():
    """Verify full dates (DD/MM/YYYY vs DD-MM-YYYY) normalize identically."""
    assert normalize_date("15/08/2026") == "15/08/2026"
    assert normalize_date("15-08-2026") == "15/08/2026"
    assert values_equivalent("15/08/2026", "15-08-2026", field_type="date") is True


def test_date_ambiguous_numeric_string_not_guessed():
    """Verify ambiguous OCR strings without date structure (e.g. 0612026) are not guessed into dates."""
    assert normalize_date("0612026") is None
    assert normalize_date("random text") is None


# ==============================================================================
# 5. String / Text Normalization Tests
# ==============================================================================

def test_text_normalization_whitespace_and_case():
    """Verify whitespace collapsing and case folding."""
    assert normalize_text("Britannia Industries") == "britannia industries"
    assert normalize_text("  britannia   industries  ") == "britannia industries"
    assert values_equivalent("Britannia Industries", "  britannia   industries  ", field_type="text") is True


def test_text_normalization_punctuation():
    """Verify conservative punctuation removal at edges."""
    assert normalize_text("Made in India.") == "made in india"
    assert normalize_text("\"Made in India\"") == "made in india"
    assert values_equivalent("Made in India.", "Made in India", field_type="text") is True


def test_text_normalization_different_companies_remain_different():
    """Verify that different companies sharing common words are NOT falsely matched."""
    assert values_equivalent(
        "Britannia Industries Ltd",
        "Parle Products Pvt Ltd",
        field_type="text"
    ) is False
    assert values_equivalent(
        "Himalayan Pure Honey",
        "Himalayan Organic Tea",
        field_type="text"
    ) is False


# ==============================================================================
# 6. Safety & Edge Cases
# ==============================================================================

def test_safety_none_handling():
    """Verify None inputs return None and do not trigger false equivalence."""
    assert normalize_mrp(None) is None
    assert normalize_quantity(None) is None
    assert normalize_unit_sale_price(None) is None
    assert normalize_date(None) is None
    assert normalize_text(None) is None

    assert values_equivalent(None, None) is False
    assert values_equivalent("250", None) is False
    assert values_equivalent(None, "500 g") is False


def test_safety_corrupted_numeric_ocr():
    """Verify corrupted OCR fragments without valid numbers are safely rejected."""
    # Isolated MRP header with no price digits
    assert normalize_mrp("मूल्य") is None
    assert normalize_mrp("MRP") is None
    assert normalize_mrp("Maximum Retail Price") is None

    # Corrupted quantity snippet without recognizable digits
    assert normalize_quantity("शुद्धमात्रा Iड० ग्राम") is None
    assert normalize_quantity("Net Qty") is None


def test_no_conflict_resolution_in_phase_3_2():
    """Verify values_equivalent purely performs boolean equivalence without modifying data or resolving conflicts."""
    result = values_equivalent(250.0, 280.0, field_type="mrp")
    assert result is False


# ==============================================================================
# 7. Phase 3.3 Evidence Fusion Engine Tests
# ==============================================================================

def test_fusion_1_same_mrp_across_two_images_corroborated():
    """1. Same MRP across two images -> corroborated, no conflict, single value."""
    cand1 = EvidenceCandidate(
        field_name="mrp",
        extracted_value="₹250",
        source_image_id=1,
        source_role="front",
        source_sequence=1,
        source_text="MRP ₹250"
    )
    cand2 = EvidenceCandidate(
        field_name="mrp",
        extracted_value="Rs. 250",
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="Rs. 250 (incl of all taxes)"
    )
    res = EvidenceFusionEngine.fuse([cand1, cand2])
    assert res.is_conflicted is False
    assert len(res.conflicts) == 0
    assert res.structured_data.mrp.value == 250.0
    assert res.structured_data.mrp.includes_taxes is True
    prov = res.provenance["mrp"]
    assert prov is not None
    assert prov.is_corroborated is True
    assert prov.has_conflict is False
    assert len(prov.corroborating_sources) == 2
    assert prov.source_image_id == 1
    assert prov.source_role == "front"


def test_fusion_2_different_mrp_across_two_images_conflict():
    """2. Different MRP across two images -> conflict, no winner selected."""
    cand1 = EvidenceCandidate(
        field_name="mrp",
        extracted_value=250.0,
        source_image_id=1,
        source_role="front",
        source_sequence=1,
        source_text="MRP 250"
    )
    cand2 = EvidenceCandidate(
        field_name="mrp",
        extracted_value=280.0,
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="MRP 280"
    )
    res = EvidenceFusionEngine.fuse([cand1, cand2])
    assert res.is_conflicted is True
    assert len(res.conflicts) == 1
    assert res.conflicts[0].field_name == "mrp"
    assert res.conflicts[0].competing_values == [250.0, 280.0]
    assert len(res.conflicts[0].sources) == 2
    # No authoritative winner selected
    assert res.structured_data.mrp.value is None
    prov = res.provenance["mrp"]
    assert prov is not None
    assert prov.has_conflict is True
    assert prov.is_corroborated is False
    assert prov.value is None
    assert len(prov.conflicts) == 1


def test_fusion_3_same_quantity_different_units_corroborated():
    """3. Same quantity with different units (500 g vs 0.5 kg) -> corroborated."""
    cand1 = EvidenceCandidate(
        field_name="net_quantity",
        extracted_value="500 g",
        source_image_id=1,
        source_role="front",
        source_sequence=1,
        source_text="Net Wt: 500 g"
    )
    cand2 = EvidenceCandidate(
        field_name="net_quantity",
        extracted_value="0.5 kg",
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="Net Weight: 0.5 kg"
    )
    res = EvidenceFusionEngine.fuse([cand1, cand2])
    assert res.is_conflicted is False
    assert res.structured_data.net_quantity.value == 500.0
    assert res.structured_data.net_quantity.unit == "g"
    prov = res.provenance["net_quantity"]
    assert prov.is_corroborated is True
    assert prov.has_conflict is False
    assert len(prov.corroborating_sources) == 2


def test_fusion_4_different_quantities_conflict():
    """4. Different quantities (500 g vs 200 g) -> conflict."""
    cand1 = EvidenceCandidate(
        field_name="net_quantity",
        extracted_value="500 g",
        source_image_id=1,
        source_role="front",
        source_sequence=1,
        source_text="500 g"
    )
    cand2 = EvidenceCandidate(
        field_name="net_quantity",
        extracted_value="200 g",
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="200 g"
    )
    res = EvidenceFusionEngine.fuse([cand1, cand2])
    assert res.is_conflicted is True
    assert len(res.conflicts) == 1
    assert res.conflicts[0].field_name == "net_quantity"
    assert res.structured_data.net_quantity.value is None
    prov = res.provenance["net_quantity"]
    assert prov.has_conflict is True
    assert prov.is_corroborated is False


def test_fusion_5_same_english_hindi_mrp_corroborated():
    """5. Same English/Hindi MRP (MRP Rs. 150 vs अधिकतम खुदरा मूल्य १५० रुपये) -> corroborated."""
    cand_eng = EvidenceCandidate(
        field_name="mrp",
        extracted_value="MRP Rs. 150",
        source_image_id=1,
        source_role="front",
        source_sequence=1,
        source_text="MRP Rs. 150",
        detected_script="LATIN"
    )
    cand_hin = EvidenceCandidate(
        field_name="mrp",
        extracted_value="अधिकतम खुदरा मूल्य १५० रुपये",
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="अधिकतम खुदरा मूल्य १५० रुपये",
        detected_script="DEVANAGARI"
    )
    res = EvidenceFusionEngine.fuse([cand_eng, cand_hin])
    assert res.is_conflicted is False
    assert res.structured_data.mrp.value == 150.0
    prov = res.provenance["mrp"]
    assert prov.is_corroborated is True
    assert len(prov.corroborating_sources) == 2


def test_fusion_6_same_english_hindi_quantity_corroborated():
    """6. Same English/Hindi quantity (Net Quantity 500 g vs शुद्ध मात्रा ५०० ग्राम) -> corroborated."""
    cand_eng = EvidenceCandidate(
        field_name="net_quantity",
        extracted_value="Net Quantity 500 g",
        source_image_id=1,
        source_role="front",
        source_sequence=1,
        source_text="Net Quantity 500 g"
    )
    cand_hin = EvidenceCandidate(
        field_name="net_quantity",
        extracted_value="शुद्ध मात्रा ५०० ग्राम",
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="शुद्ध मात्रा ५०० ग्राम"
    )
    res = EvidenceFusionEngine.fuse([cand_eng, cand_hin])
    assert res.is_conflicted is False
    assert res.structured_data.net_quantity.value == 500.0
    assert res.structured_data.net_quantity.unit == "g"
    prov = res.provenance["net_quantity"]
    assert prov.is_corroborated is True
    assert len(prov.corroborating_sources) == 2


def test_fusion_7_product_front_mrp_back_complementary():
    """7. Product on front + MRP/NetQty on back -> complementary synthesis."""
    cand1 = EvidenceCandidate(
        field_name="product_name",
        extracted_value="Himalayan Pure Honey",
        source_image_id=1,
        source_role="front",
        source_sequence=1,
        source_text="Himalayan Pure Honey"
    )
    cand2 = EvidenceCandidate(
        field_name="mrp",
        extracted_value=250.0,
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="MRP Rs. 250"
    )
    cand3 = EvidenceCandidate(
        field_name="net_quantity",
        extracted_value="500 g",
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="500 g"
    )
    cand4 = EvidenceCandidate(
        field_name="manufacturer",
        extracted_value="ABC Foods Ltd",
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="Mfd by: ABC Foods Ltd"
    )
    res = EvidenceFusionEngine.fuse([cand1, cand2, cand3, cand4])
    assert res.is_conflicted is False
    assert res.structured_data.product_name == "Himalayan Pure Honey"
    assert res.structured_data.mrp.value == 250.0
    assert res.structured_data.net_quantity.value == 500.0
    assert res.structured_data.manufacturer.name == "ABC Foods Ltd"

    # Verify provenance retains respective sources
    assert res.provenance["product_name"].source_role == "front"
    assert res.provenance["product_name"].source_image_id == 1
    assert res.provenance["mrp"].source_role == "back"
    assert res.provenance["mrp"].source_image_id == 2
    assert res.provenance["net_quantity"].source_role == "back"
    assert res.provenance["manufacturer"].source_role == "back"


def test_fusion_8_manufacturer_enrichment_across_views():
    """8. Manufacturer enrichment across views (name on front, full address on back) -> not a conflict."""
    cand1 = EvidenceCandidate(
        field_name="manufacturer",
        extracted_value="ABC Foods",
        source_image_id=1,
        source_role="front",
        source_sequence=1,
        source_text="ABC Foods"
    )
    cand2 = EvidenceCandidate(
        field_name="manufacturer",
        extracted_value="ABC Foods Pvt Ltd, Plot 10, Pune 411001",
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="Mfd by ABC Foods Pvt Ltd, Plot 10, Pune 411001"
    )
    res = EvidenceFusionEngine.fuse([cand1, cand2])
    assert res.is_conflicted is False
    assert len(res.conflicts) == 0
    prov = res.provenance["manufacturer"]
    assert prov.has_conflict is False
    # Enrichment retains both sources without false conflict
    assert len(prov.corroborating_sources) == 2
    # Consolidated value takes the enriched/more complete declaration
    assert "Plot 10, Pune 411001" in res.structured_data.manufacturer.name


def test_fusion_9_multiple_sources_retained_in_provenance():
    """9. Multiple sources retained in provenance with metadata."""
    cand1 = EvidenceCandidate(
        field_name="country_of_origin",
        extracted_value="India",
        source_image_id=1,
        source_role="front",
        source_sequence=1,
        source_text="Made in India",
        confidence=0.98,
        detected_script="LATIN"
    )
    cand2 = EvidenceCandidate(
        field_name="country_of_origin",
        extracted_value="India",
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="Country of Origin: India",
        confidence=0.94,
        detected_script="LATIN"
    )
    res = EvidenceFusionEngine.fuse([cand1, cand2])
    prov = res.provenance["country_of_origin"]
    assert prov.is_corroborated is True
    assert len(prov.corroborating_sources) == 2
    assert prov.corroborating_sources[0].source_image_id == 1
    assert prov.corroborating_sources[0].source_role == "front"
    assert prov.corroborating_sources[1].source_image_id == 2
    assert prov.corroborating_sources[1].source_role == "back"


def test_fusion_10_conflict_retains_both_source_records():
    """10. Conflict retains both source records with full metadata."""
    cand1 = EvidenceCandidate(
        field_name="mrp",
        extracted_value="Rs. 250",
        source_image_id=10,
        source_role="front",
        source_sequence=1,
        source_text="MRP Rs. 250"
    )
    cand2 = EvidenceCandidate(
        field_name="mrp",
        extracted_value="Rs. 280",
        source_image_id=20,
        source_role="back",
        source_sequence=2,
        source_text="MRP Rs. 280"
    )
    res = EvidenceFusionEngine.fuse([cand1, cand2])
    assert len(res.conflicts) == 1
    conflict = res.conflicts[0]
    assert len(conflict.sources) == 2
    assert conflict.sources[0].source_image_id == 10
    assert conflict.sources[1].source_image_id == 20
    assert conflict.sources[0].source_text == "MRP Rs. 250"
    assert conflict.sources[1].source_text == "MRP Rs. 280"


def test_fusion_11_phone_number_cannot_become_mrp():
    """11. Phone numbers must never be accepted as MRP candidates."""
    cand_phone = EvidenceCandidate(
        field_name="mrp",
        extracted_value="1800-444-5555",
        source_image_id=1,
        source_role="back",
        source_sequence=1,
        source_text="Toll Free: 1800-444-5555"
    )
    res = EvidenceFusionEngine.fuse([cand_phone])
    assert res.structured_data.mrp.value is None
    assert res.provenance["mrp"] is None
    assert res.is_conflicted is False


def test_fusion_12_batch_number_cannot_become_mrp():
    """12. Batch numbers must never be accepted as MRP candidates."""
    cand_batch = EvidenceCandidate(
        field_name="mrp",
        extracted_value="Batch No. 2026",
        source_image_id=1,
        source_role="back",
        source_sequence=1,
        source_text="Batch No. 2026"
    )
    res = EvidenceFusionEngine.fuse([cand_batch])
    assert res.structured_data.mrp.value is None
    assert res.provenance["mrp"] is None
    assert res.is_conflicted is False


def test_fusion_13_missing_values_ignored_not_treated_as_conflicts():
    """13. Missing values from other images are ignored and never treated as conflicts."""
    cand1 = EvidenceCandidate(
        field_name="mrp",
        extracted_value=250.0,
        source_image_id=1,
        source_role="front",
        source_sequence=1,
        source_text="MRP 250"
    )
    cand_none = EvidenceCandidate(
        field_name="mrp",
        extracted_value=None,
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text=None
    )
    res = EvidenceFusionEngine.fuse([cand1, cand_none])
    assert res.is_conflicted is False
    assert len(res.conflicts) == 0
    assert res.structured_data.mrp.value == 250.0
    prov = res.provenance["mrp"]
    assert prov.has_conflict is False
    assert prov.is_corroborated is False
    assert len(prov.corroborating_sources) == 1


def test_fusion_14_three_matching_sources_all_retained():
    """14. Three matching sources -> all three retained in corroborating_sources."""
    cand1 = EvidenceCandidate(
        field_name="mrp",
        extracted_value="₹250",
        source_image_id=1,
        source_role="front",
        source_sequence=1,
        source_text="₹250"
    )
    cand2 = EvidenceCandidate(
        field_name="mrp",
        extracted_value="Rs. 250",
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="Rs. 250"
    )
    cand3 = EvidenceCandidate(
        field_name="mrp",
        extracted_value="२५०",
        source_image_id=3,
        source_role="label",
        source_sequence=3,
        source_text="२५०"
    )
    res = EvidenceFusionEngine.fuse([cand1, cand2, cand3])
    assert res.is_conflicted is False
    assert res.structured_data.mrp.value == 250.0
    prov = res.provenance["mrp"]
    assert prov.is_corroborated is True
    assert len(prov.corroborating_sources) == 3
    source_ids = {s.source_image_id for s in prov.corroborating_sources}
    assert source_ids == {1, 2, 3}


def test_fusion_15_two_matching_one_conflicting_conflict_retained_no_winner():
    """15. Two matching + one conflicting source -> conflict retained; no majority winner selected."""
    cand1 = EvidenceCandidate(
        field_name="mrp",
        extracted_value=250.0,
        source_image_id=1,
        source_role="front",
        source_sequence=1,
        source_text="MRP 250"
    )
    cand2 = EvidenceCandidate(
        field_name="mrp",
        extracted_value="₹250",
        source_image_id=2,
        source_role="back",
        source_sequence=2,
        source_text="MRP ₹250"
    )
    cand3 = EvidenceCandidate(
        field_name="mrp",
        extracted_value=280.0,
        source_image_id=3,
        source_role="side",
        source_sequence=3,
        source_text="MRP 280"
    )
    res = EvidenceFusionEngine.fuse([cand1, cand2, cand3])
    assert res.is_conflicted is True
    assert len(res.conflicts) == 1
    conflict = res.conflicts[0]
    assert len(conflict.sources) == 3
    assert conflict.competing_values == [250.0, 280.0]
    # Critical invariant: no majority voting winner selected on contradiction
    assert res.structured_data.mrp.value is None
    prov = res.provenance["mrp"]
    assert prov.has_conflict is True
    assert prov.value is None
    assert len(prov.conflicts) == 1

