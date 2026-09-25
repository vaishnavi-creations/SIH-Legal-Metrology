import logging
from typing import Dict, Any, List, Optional
from app.schemas.product import StructuredProductData
from app.rules.base import BaseRule
from app.rules.models import (
    RuleStatus,
    ComplianceStatus,
    Severity,
    RuleCheckResult,
    Violation,
    RuleWarning,
    ComplianceReport
)
from app.rules.declarations import (
    RuleManufacturerDetails,
    RuleCommodityName,
    RuleNetQuantity,
    RuleDateOfManufacture,
    RuleMaximumRetailPrice,
    RuleConsumerCare,
    RuleCountryOfOrigin,
    RuleUnitSalePrice
)

logger = logging.getLogger(__name__)

class LegalMetrologyRuleEngine:
    """
    Deterministic, auditable rule engine that verifies packaged commodity declarations
    against the Legal Metrology (Packaged Commodities) Rules, 2011 and official amendments.
    Zero hallucination: Every pass, violation, or warning strictly cites the statutory clause.
    """

    def __init__(self):
        # Register standard statutory rules
        self.rules: List[BaseRule] = [
            RuleManufacturerDetails(),
            RuleCommodityName(),
            RuleNetQuantity(),
            RuleDateOfManufacture(),
            RuleMaximumRetailPrice(),
            RuleConsumerCare(),
            RuleCountryOfOrigin(),
            RuleUnitSalePrice()
        ]

    def check_exemptions(self, product: StructuredProductData, context: Dict[str, Any]) -> List[str]:
        """
        Evaluates statutory exemptions under Rule 26.
        """
        exemptions = []
        net_qty = product.net_quantity.value
        unit = product.net_quantity.unit.lower() if product.net_quantity.unit else None

        # Rule 26(a): Package containing net weight or measure of 10 g or 10 ml or less
        # (Provided that this exemption does not apply to tobacco and tobacco products)
        commodity_type = context.get("commodity_type", "").lower()
        is_tobacco = "tobacco" in commodity_type or "gutkha" in commodity_type

        if net_qty is not None and unit in {"g", "ml"} and net_qty <= 10.0 and not is_tobacco:
            context["exemption_rule_26_a"] = True
            exemptions.append(
                f"Rule 26(a) Exemption: Package net quantity is {net_qty} {unit} (<= 10g/10ml). "
                "Exempted from standard Chapter II labeling declarations."
            )

        return exemptions

    def evaluate_compliance(
        self,
        product: StructuredProductData,
        context: Optional[Dict[str, Any]] = None
    ) -> ComplianceReport:
        """
        Executes all registered legal rules deterministically against the structured product data.
        Returns a comprehensive, fully explainable ComplianceReport.
        """
        ctx = dict(context or {})

        # 1. Evaluate statutory exemptions
        exemptions_applied = self.check_exemptions(product, ctx)

        checks: List[RuleCheckResult] = []
        violations: List[Violation] = []
        warnings: List[RuleWarning] = []
        missing_declarations: List[str] = []

        rules_passed = 0
        rules_failed = 0
        rules_insufficient = 0
        rules_not_applicable = 0

        # Determine Chapter II applicability
        chapter_ii_applicable = True
        chapter_ii_basis = "Rule 3(b)"
        if context:
            if context.get("chapter_ii_applicable") is False:
                chapter_ii_applicable = False
            elif "context_provenance" in context and isinstance(context["context_provenance"], dict):
                stat_det = context["context_provenance"].get("statutory_determination")
                if isinstance(stat_det, dict):
                    if stat_det.get("chapter_ii_applicable") is False:
                        chapter_ii_applicable = False
                    if stat_det.get("statutory_basis"):
                        chapter_ii_basis = stat_det["statutory_basis"]

        # 2. Iterate through all registered statutory rules
        for rule in self.rules:
            if not chapter_ii_applicable:
                rules_not_applicable += 1
                checks.append(
                    RuleCheckResult(
                        rule_id=rule.rule_id,
                        legal_reference=rule.legal_reference,
                        field_checked=rule.field_checked,
                        extracted_value=None,
                        expected_requirement=rule.description,
                        status=RuleStatus.NOT_APPLICABLE,
                        explanation=f"Chapter II not applicable under {chapter_ii_basis}."
                    )
                )
                continue

            if not rule.is_applicable(product, ctx):
                rules_not_applicable += 1
                checks.append(
                    RuleCheckResult(
                        rule_id=rule.rule_id,
                        legal_reference=rule.legal_reference,
                        field_checked=rule.field_checked,
                        extracted_value=None,
                        expected_requirement=rule.description,
                        status=RuleStatus.NOT_APPLICABLE,
                        explanation=f"Rule not applicable to this package ({rule.rule_id})."
                    )
                )
                continue

            # Evaluate the rule
            result = rule.evaluate(product, ctx)
            checks.append(result)

            if result.status == RuleStatus.PASS:
                rules_passed += 1
            elif result.status == RuleStatus.FAIL:
                rules_failed += 1
                severity = Severity.CRITICAL if rule.rule_id in {"LMR-06-1-E", "LMR-06-1-C", "LMR-06-1-A"} else Severity.HIGH
                violations.append(
                    Violation(
                        rule_id=result.rule_id,
                        legal_reference=result.legal_reference,
                        field=result.field_checked,
                        severity=severity,
                        message=result.explanation
                    )
                )
                if result.extracted_value is None:
                    missing_declarations.append(result.field_checked)
            elif result.status == RuleStatus.WARNING:
                rules_passed += 1  # Warnings pass statutory check with an advisory
                warnings.append(
                    RuleWarning(
                        rule_id=result.rule_id,
                        legal_reference=result.legal_reference,
                        field=result.field_checked,
                        message=result.explanation
                    )
                )
            elif result.status == RuleStatus.INSUFFICIENT_DATA:
                rules_insufficient += 1
                missing_declarations.append(result.field_checked)

        # 3. Determine Overall Compliance Status
        total_applicable = rules_passed + rules_failed + rules_insufficient

        if not chapter_ii_applicable:
            compliance_status = ComplianceStatus.NOT_APPLICABLE
            summary = (
                f"NOT APPLICABLE: Package qualifies for Chapter II exclusion under {chapter_ii_basis}. "
                "Standard retail packaging declarations do not govern this package."
            )
        elif exemptions_applied and rules_failed == 0:
            compliance_status = ComplianceStatus.COMPLIANT
            summary = (
                f"COMPLIANT (Exempted): Product qualifies for statutory exemption: {'; '.join(exemptions_applied)}. "
                f"{rules_passed} applicable checks verified."
            )
        elif rules_failed > 0:
            compliance_status = ComplianceStatus.NON_COMPLIANT
            violation_fields = [v.field for v in violations]
            summary = (
                f"NON-COMPLIANT: Found {rules_failed} statutory violation(s) under Legal Metrology Rules, 2011 "
                f"in field(s): {', '.join(violation_fields)}. {rules_passed} of {total_applicable} checks passed."
            )
        elif rules_insufficient > 0:
            compliance_status = ComplianceStatus.INSUFFICIENT_DATA
            summary = (
                f"INSUFFICIENT DATA: Scan did not capture enough clear label text to verify {rules_insufficient} "
                f"mandatory declaration(s): {', '.join(missing_declarations)}. Please rescanning with better lighting."
            )
        else:
            compliance_status = ComplianceStatus.COMPLIANT
            summary = (
                f"FULLY COMPLIANT: All {rules_passed} applicable declarations satisfy the "
                "Legal Metrology (Packaged Commodities) Rules, 2011."
            )

        return ComplianceReport(
            compliance_status=compliance_status,
            summary=summary,
            rules_checked=len(self.rules),
            rules_passed=rules_passed,
            rules_failed=rules_failed,
            rules_insufficient_data=rules_insufficient,
            rules_not_applicable=rules_not_applicable,
            violations=violations,
            warnings=warnings,
            missing_declarations=missing_declarations,
            exemptions_applied=exemptions_applied,
            checks=checks
        )

rule_engine = LegalMetrologyRuleEngine()
