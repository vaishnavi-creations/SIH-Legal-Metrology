import re
from typing import Dict, Any, Optional, Union
from app.schemas.product import StructuredProductData, UnitSalePriceDetails
from app.rules.base import BaseRule
from app.rules.models import RuleCheckResult, RuleStatus



STANDARD_LEGAL_UNITS = {
    # Weight (Second Schedule)
    "g", "kg", "mg",
    # Volume (Second Schedule)
    "ml", "l", "kl",
    # Length / Area (Second Schedule)
    "m", "cm", "mm", "km", "sq m",
    # Number
    "pcs", "pieces", "units", "u", "n", "number"
}

NON_STANDARD_UNIT_WARNINGS = {
    "gm": "Standard abbreviation under Rule 11 / Second Schedule is 'g', not 'gm'.",
    "gms": "Standard abbreviation under Rule 11 / Second Schedule is 'g', not 'gms'.",
    "kilo": "Standard abbreviation under Rule 11 is 'kg'.",
    "kilos": "Standard abbreviation under Rule 11 is 'kg'.",
    "ltr": "Standard abbreviation under Rule 11 is 'l' or 'L'.",
    "ltrs": "Standard abbreviation under Rule 11 is 'l' or 'L'.",
    "liters": "Standard abbreviation under Rule 11 is 'l' or 'L'.",
    "litres": "Standard abbreviation under Rule 11 is 'l' or 'L'."
}

class RuleManufacturerDetails(BaseRule):
    """
    Rule 6(1)(a): Name and complete address of the manufacturer, packer, or importer.
    """
    def __init__(self):
        super().__init__(
            rule_id="LMR-06-1-A",
            legal_reference="Rule 6(1)(a) of Legal Metrology (Packaged Commodities) Rules, 2011",
            description="Name and complete postal address of manufacturer, packer, or importer including postal PIN code.",
            field_checked="manufacturer"
        )

    def is_applicable(self, product: StructuredProductData, context: Dict[str, Any]) -> bool:
        # Check if small package exemption applies (Rule 26(a): <= 10g or <= 10ml)
        if context.get("exemption_rule_26_a"):
            return False
        return True

    def evaluate(self, product: StructuredProductData, context: Dict[str, Any]) -> RuleCheckResult:
        mfg = product.manufacturer
        name = mfg.name.strip() if mfg.name else None
        addr = mfg.address.strip() if mfg.address else None
        pincode = mfg.pincode.strip() if mfg.pincode else None

        # Check if no data was captured at all
        if not name and not addr and not mfg.raw_text:
            if context.get("is_incomplete_scan", False):
                return self.create_result(
                    status=RuleStatus.INSUFFICIENT_DATA,
                    extracted_value=None,
                    expected_requirement="Name and complete address of manufacturer/packer/importer.",
                    explanation="No manufacturer information detected in scan. Image may be partial or blurry."
                )
            return self.create_result(
                status=RuleStatus.FAIL,
                extracted_value=None,
                expected_requirement="Name and complete address of manufacturer/packer/importer.",
                explanation="Violation of Rule 6(1)(a): Missing name and address of the manufacturer, packer, or importer."
            )

        # Name is mandatory
        if not name:
            return self.create_result(
                status=RuleStatus.FAIL,
                extracted_value={"address": addr, "pincode": pincode},
                expected_requirement="Name of the manufacturer, packer, or importer.",
                explanation="Violation of Rule 6(1)(a): Manufacturer name is missing, only address details were found."
            )

        # Complete address with PIN code
        if not addr and not pincode:
            return self.create_result(
                status=RuleStatus.FAIL,
                extracted_value=name,
                expected_requirement="Complete postal address with 6-digit PIN code.",
                explanation=f"Violation of Rule 6(1)(a): Manufacturer '{name}' is declared, but address and postal PIN code are missing."
            )

        if not pincode:
            return self.create_result(
                status=RuleStatus.WARNING,
                extracted_value={"name": name, "address": addr},
                expected_requirement="Complete address including 6-digit PIN code.",
                explanation=f"Advisory under Rule 6(1)(a): Address for '{name}' is present, but 6-digit postal PIN code was not clearly detected."
            )

        return self.create_result(
            status=RuleStatus.PASS,
            extracted_value={"name": name, "address": addr, "pincode": pincode},
            expected_requirement="Name and complete address of manufacturer/packer.",
            explanation=f"Compliant: '{name}' with address and PIN code {pincode} verified."
        )


class RuleCommodityName(BaseRule):
    """
    Rule 6(1)(b): Generic or common name of the commodity.
    """
    def __init__(self):
        super().__init__(
            rule_id="LMR-06-1-B",
            legal_reference="Rule 6(1)(b) of Legal Metrology (Packaged Commodities) Rules, 2011",
            description="The common or generic name of the commodity contained in the package.",
            field_checked="common_or_generic_name"
        )

    def is_applicable(self, product: StructuredProductData, context: Dict[str, Any]) -> bool:
        if context.get("exemption_rule_26_a"):
            return False
        return True

    def evaluate(self, product: StructuredProductData, context: Dict[str, Any]) -> RuleCheckResult:
        generic_name = product.common_or_generic_name
        product_name = product.product_name

        name_to_check = generic_name or product_name

        if not name_to_check:
            if context.get("is_incomplete_scan", False):
                return self.create_result(
                    status=RuleStatus.INSUFFICIENT_DATA,
                    extracted_value=None,
                    expected_requirement="Common or generic name of the commodity.",
                    explanation="No commodity name could be detected in the scanned text."
                )
            return self.create_result(
                status=RuleStatus.FAIL,
                extracted_value=None,
                expected_requirement="Common or generic name of the commodity.",
                explanation="Violation of Rule 6(1)(b): Missing common or generic name of the commodity."
            )

        return self.create_result(
            status=RuleStatus.PASS,
            extracted_value=name_to_check,
            expected_requirement="Common or generic name of the commodity.",
            explanation=f"Compliant: Commodity name declared as '{name_to_check}'."
        )


class RuleNetQuantity(BaseRule):
    """
    Rule 6(1)(c) and Rule 11: Net quantity in standard legal units of weight, measure, or number.
    """
    def __init__(self):
        super().__init__(
            rule_id="LMR-06-1-C",
            legal_reference="Rule 6(1)(c) & Rule 11 of Legal Metrology (Packaged Commodities) Rules, 2011",
            description="Net quantity stated in standard units of weight/measure (g, kg, ml, l) or number.",
            field_checked="net_quantity"
        )

    def is_applicable(self, product: StructuredProductData, context: Dict[str, Any]) -> bool:
        if context.get("exemption_rule_26_a"):
            return False
        return True

    def evaluate(self, product: StructuredProductData, context: Dict[str, Any]) -> RuleCheckResult:
        net_qty = product.net_quantity
        val = net_qty.value
        unit = net_qty.unit.lower() if net_qty.unit else None
        piece_count = net_qty.piece_count

        if val is None and piece_count is None:
            if context.get("is_incomplete_scan", False):
                return self.create_result(
                    status=RuleStatus.INSUFFICIENT_DATA,
                    extracted_value=None,
                    expected_requirement="Net quantity in standard units of weight, measure, or piece count.",
                    explanation="Net quantity could not be determined from the scanned image."
                )
            return self.create_result(
                status=RuleStatus.FAIL,
                extracted_value=None,
                expected_requirement="Net quantity in standard units of weight, measure, or piece count.",
                explanation="Violation of Rule 6(1)(c): Mandatory Net Quantity declaration is missing."
            )

        # Check unit validity under Rule 11 / Second Schedule
        if unit:
            if unit in NON_STANDARD_UNIT_WARNINGS:
                return self.create_result(
                    status=RuleStatus.WARNING,
                    extracted_value=f"{val} {unit}",
                    expected_requirement="Standard unit of weight or measure (Second Schedule).",
                    explanation=f"Non-standard unit '{unit}': {NON_STANDARD_UNIT_WARNINGS[unit]}"
                )
            elif unit not in STANDARD_LEGAL_UNITS:
                return self.create_result(
                    status=RuleStatus.FAIL,
                    extracted_value=f"{val} {unit}",
                    expected_requirement=f"Standard unit of measurement from Second Schedule: {', '.join(sorted(STANDARD_LEGAL_UNITS))}.",
                    explanation=f"Violation of Rule 11: Unit '{unit}' is not an authorized standard unit of measurement."
                )

        extracted_repr = f"{val} {unit}" if val is not None and unit else f"{piece_count} items"
        return self.create_result(
            status=RuleStatus.PASS,
            extracted_value=extracted_repr,
            expected_requirement="Net quantity in standard units.",
            explanation=f"Compliant: Net quantity verified as '{extracted_repr}'."
        )


class RuleDateOfManufacture(BaseRule):
    """
    Rule 6(1)(d): Month and year of manufacture or pre-packing or import.
    """
    def __init__(self):
        super().__init__(
            rule_id="LMR-06-1-D",
            legal_reference="Rule 6(1)(d) of Legal Metrology (Packaged Commodities) Rules, 2011",
            description="The month and year in which commodity is manufactured, pre-packed, or imported.",
            field_checked="dates"
        )

    def is_applicable(self, product: StructuredProductData, context: Dict[str, Any]) -> bool:
        if context.get("exemption_rule_26_a"):
            return False
        return True

    def evaluate(self, product: StructuredProductData, context: Dict[str, Any]) -> RuleCheckResult:
        mfg_date = getattr(product.dates, "manufacturing_date", None)
        pkg_date = getattr(product.dates, "packaging_date", None) or getattr(product.dates, "packing_date", None)
        date_declared = mfg_date or pkg_date or getattr(product.dates, "raw_text", None)

        if not date_declared:

            if context.get("is_incomplete_scan", False):
                return self.create_result(
                    status=RuleStatus.INSUFFICIENT_DATA,
                    extracted_value=None,
                    expected_requirement="Month and year of manufacture or packing (e.g. MM/YYYY).",
                    explanation="Date of manufacture/packing could not be detected from the scanned text."
                )
            return self.create_result(
                status=RuleStatus.FAIL,
                extracted_value=None,
                expected_requirement="Month and year of manufacture, packing, or import (e.g. MM/YYYY).",
                explanation="Violation of Rule 6(1)(d): Missing Month and Year of manufacture or pre-packing."
            )

        return self.create_result(
            status=RuleStatus.PASS,
            extracted_value=date_declared,
            expected_requirement="Month and year of manufacture or packing.",
            explanation=f"Compliant: Date of manufacture/packing declared as '{date_declared}'."
        )


class RuleMaximumRetailPrice(BaseRule):
    """
    Rule 6(1)(e): Maximum Retail Price inclusive of all taxes.
    """
    def __init__(self):
        super().__init__(
            rule_id="LMR-06-1-E",
            legal_reference="Rule 6(1)(e) of Legal Metrology (Packaged Commodities) Rules, 2011",
            description="Retail sale price stated as Maximum Retail Price (MRP) Rs./₹ ... inclusive of all taxes.",
            field_checked="mrp"
        )

    def is_applicable(self, product: StructuredProductData, context: Dict[str, Any]) -> bool:
        if context.get("exemption_rule_26_a"):
            return False
        return True

    def evaluate(self, product: StructuredProductData, context: Dict[str, Any]) -> RuleCheckResult:
        mrp = product.mrp
        val = mrp.value
        includes_taxes = mrp.includes_taxes if mrp.includes_taxes is not None else getattr(mrp, "inclusive_of_taxes", None)
        raw_text = mrp.raw_text or ""


        if val is None:
            if context.get("is_incomplete_scan", False):
                return self.create_result(
                    status=RuleStatus.INSUFFICIENT_DATA,
                    extracted_value=None,
                    expected_requirement="Maximum Retail Price (MRP) inclusive of all taxes.",
                    explanation="MRP value could not be detected from the package image."
                )
            return self.create_result(
                status=RuleStatus.FAIL,
                extracted_value=None,
                expected_requirement="Maximum Retail Price (MRP) inclusive of all taxes.",
                explanation="Violation of Rule 6(1)(e): Mandatory Retail Sale Price (MRP) declaration is missing."
            )

        if val <= 0:
            return self.create_result(
                status=RuleStatus.FAIL,
                extracted_value=val,
                expected_requirement="Valid positive retail sale price.",
                explanation=f"Violation of Rule 6(1)(e): Declared price value '{val}' is invalid."
            )

        # Taxes extra is explicitly illegal
        if includes_taxes is False or re.search(r'taxes\s*extra|plus\s*taxes', raw_text, re.IGNORECASE):
            return self.create_result(
                status=RuleStatus.FAIL,
                extracted_value=f"Rs. {val} (taxes extra)",
                expected_requirement="Price must be inclusive of all taxes.",
                explanation="Violation of Rule 6(1)(e): Charging or stating taxes separately/extra is strictly prohibited."
            )

        # Check for mandatory "incl. of all taxes"
        has_tax_phrase = (
            includes_taxes is True or
            bool(re.search(r'(?:incl|inclusive)\.?\s*(?:of)?\s*all\s*taxes', raw_text, re.IGNORECASE))
        )

        if not has_tax_phrase:
            return self.create_result(
                status=RuleStatus.FAIL,
                extracted_value=f"Rs. {val}",
                expected_requirement="MRP must explicitly state '(inclusive of all taxes)' or 'incl. of all taxes'.",
                explanation=f"Violation of Rule 6(1)(e): Price of Rs. {val} is stated without the mandatory declaration '(inclusive of all taxes)'."
            )

        return self.create_result(
            status=RuleStatus.PASS,
            extracted_value=f"Rs. {val:.2f} (inclusive of all taxes)",
            expected_requirement="MRP inclusive of all taxes.",
            explanation=f"Compliant: MRP declared as Rs. {val:.2f} (inclusive of all taxes)."
        )


class RuleConsumerCare(BaseRule):
    """
    Rule 6(1)(n): Consumer grievance redressal details (Name, address, phone, email).
    """
    def __init__(self):
        super().__init__(
            rule_id="LMR-06-1-N",
            legal_reference="Rule 6(1)(n) of Legal Metrology (Packaged Commodities) Rules, 2011",
            description="Consumer complaint redressal contact details (telephone number and/or email address).",
            field_checked="consumer_care"
        )

    def is_applicable(self, product: StructuredProductData, context: Dict[str, Any]) -> bool:
        if context.get("exemption_rule_26_a"):
            return False
        return True

    def evaluate(self, product: StructuredProductData, context: Dict[str, Any]) -> RuleCheckResult:
        care = product.consumer_care
        phone = care.phone.strip() if care.phone else None
        email = care.email.strip() if care.email else None

        if not phone and not email and not care.raw_text:
            if context.get("is_incomplete_scan", False):
                return self.create_result(
                    status=RuleStatus.INSUFFICIENT_DATA,
                    extracted_value=None,
                    expected_requirement="Consumer grievance contact details: telephone and/or email.",
                    explanation="No consumer care details detected in the scan."
                )
            return self.create_result(
                status=RuleStatus.FAIL,
                extracted_value=None,
                expected_requirement="Consumer care telephone number and email address.",
                explanation="Violation of Rule 6(1)(n): Missing consumer complaint redressal details."
            )

        # Both present -> Excellent compliance
        if phone and email:
            return self.create_result(
                status=RuleStatus.PASS,
                extracted_value={"phone": phone, "email": email},
                expected_requirement="Consumer care telephone and email.",
                explanation=f"Compliant: Consumer care phone ({phone}) and email ({email}) verified."
            )

        # Only one present -> Pass with advisory warning
        found_mode = f"phone: {phone}" if phone else f"email: {email}"
        missing_mode = "email address" if phone else "telephone/toll-free number"
        return self.create_result(
            status=RuleStatus.PASS,
            extracted_value={"phone": phone, "email": email},
            expected_requirement="Consumer care telephone number and email address.",
            explanation=f"Compliant with advisory: Consumer care {found_mode} present, but {missing_mode} was not clearly detected."
        )


class RuleCountryOfOrigin(BaseRule):
    """
    Rule 6(10): Country of origin on imported packages.
    """
    def __init__(self):
        super().__init__(
            rule_id="LMR-06-10",
            legal_reference="Rule 6(10) of Legal Metrology (Packaged Commodities) Rules, 2011",
            description="Declaration of country of origin or manufacture for imported packages.",
            field_checked="country_of_origin"
        )

    def is_applicable(self, product: StructuredProductData, context: Dict[str, Any]) -> bool:
        # Applicable if imported flag is set, or if entity type is importer, or if declared
        is_imported = context.get("is_imported", False)
        if product.manufacturer and product.manufacturer.entity_type == "importer":
            is_imported = True
        return is_imported or bool(product.country_of_origin)

    def evaluate(self, product: StructuredProductData, context: Dict[str, Any]) -> RuleCheckResult:
        origin = product.country_of_origin
        is_imported = context.get("is_imported", False) or (
            product.manufacturer and product.manufacturer.entity_type == "importer"
        )

        if not origin:
            if is_imported:
                return self.create_result(
                    status=RuleStatus.FAIL,
                    extracted_value=None,
                    expected_requirement="Country of origin or manufacture for imported packages.",
                    explanation="Violation of Rule 6(10): Package is imported or handled by importer, but Country of Origin is not declared."
                )
            return self.create_result(
                status=RuleStatus.NOT_APPLICABLE,
                extracted_value=None,
                expected_requirement="Country of origin mandatory for imported goods.",
                explanation="Domestic product without imported declaration. Rule 6(10) requirement satisfied."
            )

        return self.create_result(
            status=RuleStatus.PASS,
            extracted_value=origin,
            expected_requirement="Declaration of country of origin.",
            explanation=f"Compliant: Country of origin verified as '{origin}'."
        )


class RuleUnitSalePrice(BaseRule):
    """
    Rule 6(11): Unit Sale Price (USP) declaration (as amended by 2021 Amendment Rules).
    Mandatory for retail packages where net quantity > 1 kg / 1 L (price per kg/l)
    or < 1 kg / 1 L (price per g/ml). Exempt if net quantity is exactly 1 kg, 1 L, or 1 item.
    """
    def __init__(self):
        super().__init__(
            rule_id="LMR-06-11",
            legal_reference="Rule 6(11) of Legal Metrology (Packaged Commodities) Rules, 2011 (2021 Amendment)",
            description="Unit Sale Price (USP) per g/ml (for packages < 1kg/1L) or per kg/l (for packages > 1kg/1L).",
            field_checked="unit_sale_price"
        )

    def is_applicable(self, product: StructuredProductData, context: Dict[str, Any]) -> bool:
        if context.get("exemption_rule_26_a"):
            return False

        qty = product.net_quantity.value
        unit = product.net_quantity.unit.lower() if product.net_quantity.unit else None

        if qty is None or not unit:
            return False

        # Exemption: packages containing exactly 1 kg, 1 liter, or 1 piece
        if (unit in {"kg", "l"} and qty == 1.0) or (unit in {"pcs", "units", "n"} and qty == 1.0):
            return False

        # Applicable to standard retail packaging
        return True

    def evaluate(self, product: StructuredProductData, context: Dict[str, Any]) -> RuleCheckResult:
        usp_candidate = getattr(product, "unit_sale_price", None) or getattr(product.mrp, "unit_sale_price", None)
        qty = product.net_quantity.value
        unit = product.net_quantity.unit

        usp_display = None
        if isinstance(usp_candidate, UnitSalePriceDetails):
            if usp_candidate.value is not None:
                usp_unit = usp_candidate.unit or ""
                usp_display = f"Rs. {usp_candidate.value:.2f} / {usp_unit}".strip()
            else:
                usp_display = usp_candidate.raw_text
        elif isinstance(usp_candidate, dict):
            if usp_candidate.get("value") is not None:
                usp_unit = usp_candidate.get("unit") or ""
                usp_display = f"Rs. {usp_candidate.get('value')} / {usp_unit}".strip()
            else:
                usp_display = usp_candidate.get("raw_text")
        elif isinstance(usp_candidate, str) and usp_candidate.strip():
            usp_display = usp_candidate.strip()

        if not usp_display:
            return self.create_result(
                status=RuleStatus.FAIL,
                extracted_value=None,
                expected_requirement="Unit Sale Price (e.g. 'Rs. ... per g' or 'Rs. ... per kg').",
                explanation=f"Violation of Rule 6(11): Package of {qty} {unit} requires Unit Sale Price (USP) declaration, which was not found."
            )

        return self.create_result(
            status=RuleStatus.PASS,
            extracted_value=usp_display,
            expected_requirement="Unit Sale Price declaration.",
            explanation=f"Compliant: Unit Sale Price verified as '{usp_display}'."
        )

