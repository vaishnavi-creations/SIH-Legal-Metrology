from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from app.schemas.product import StructuredProductData

class RuleStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    WARNING = "WARNING"
    EXEMPT = "EXEMPT"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"

class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EXEMPT = "EXEMPT"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class RuleCheckResult(BaseModel):
    rule_id: str = Field(..., description="Unique code for the rule (e.g. LMR-001)")
    legal_reference: str = Field(..., description="Statutory clause in Legal Metrology (Packaged Commodities) Rules, 2011")
    field_checked: str = Field(..., description="Name of the product declaration field checked")
    extracted_value: Optional[Any] = Field(None, description="The actual value extracted from the package")
    expected_requirement: str = Field(..., description="Description of the legal requirement")
    status: RuleStatus = Field(..., description="Evaluation outcome: PASS, FAIL, INSUFFICIENT_DATA, NOT_APPLICABLE, WARNING")
    explanation: str = Field(..., description="Detailed explanation of why this check passed, failed, or lacked data")

class Violation(BaseModel):
    rule_id: str = Field(..., description="Rule identifier")
    legal_reference: str = Field(..., description="Exact statutory clause")
    field: str = Field(..., description="Field with non-compliance")
    severity: Severity = Field(Severity.HIGH, description="Violation severity level")
    message: str = Field(..., description="Clear explanation of the violation")

class RuleWarning(BaseModel):
    rule_id: str = Field(..., description="Rule identifier")
    legal_reference: str = Field(..., description="Exact statutory clause")
    field: str = Field(..., description="Field with advisory warning")
    message: str = Field(..., description="Advisory message or suggested correction")

class ComplianceReport(BaseModel):
    compliance_status: ComplianceStatus = Field(..., description="Overall compliance status: COMPLIANT, NON_COMPLIANT, INSUFFICIENT_DATA")
    summary: str = Field(..., description="Human-readable legal compliance overview")
    rules_checked: int = Field(..., description="Total number of applicable rules evaluated")
    rules_passed: int = Field(..., description="Count of rules that passed")
    rules_failed: int = Field(..., description="Count of rules that failed (violations)")
    rules_insufficient_data: int = Field(..., description="Count of rules with insufficient data")
    rules_not_applicable: int = Field(..., description="Count of rules marked not applicable (e.g. exemptions)")
    violations: List[Violation] = Field(default_factory=list, description="List of statutory violations found")
    warnings: List[RuleWarning] = Field(default_factory=list, description="List of advisory warnings found")
    missing_declarations: List[str] = Field(default_factory=list, description="Mandatory declarations that are absent")
    exemptions_applied: List[str] = Field(default_factory=list, description="Exemptions identified under Rule 26 or other clauses")
    checks: List[RuleCheckResult] = Field(default_factory=list, description="Detailed item-by-item audit of all checks")

class ComplianceCheckRequest(BaseModel):
    data: Optional[StructuredProductData] = Field(None, description="Structured product data from Phase 4")
    file_id: Optional[str] = Field(None, description="File ID of an already uploaded/scanned image")
    is_imported: Optional[bool] = Field(None, description="Explicit flag indicating if product is imported (triggers Rule 6(10))")
    commodity_type: Optional[str] = Field(None, description="Type of commodity (e.g. food, cosmetics, industrial, electronics)")
