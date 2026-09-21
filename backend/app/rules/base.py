from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.schemas.product import StructuredProductData
from app.rules.models import RuleCheckResult, RuleStatus

class BaseRule(ABC):
    """
    Abstract base class for a Legal Metrology (Packaged Commodities) Rule check.
    Encapsulates rule identity, legal authority reference, applicability logic, and evaluation.
    """

    def __init__(
        self,
        rule_id: str,
        legal_reference: str,
        description: str,
        field_checked: str
    ):
        self.rule_id = rule_id
        self.legal_reference = legal_reference
        self.description = description
        self.field_checked = field_checked

    @abstractmethod
    def is_applicable(self, product: StructuredProductData, context: Dict[str, Any]) -> bool:
        """
        Determines if this rule applies to the given packaged commodity based on
        commodity type, net quantity, origin, packaging status, etc.
        """
        pass

    @abstractmethod
    def evaluate(self, product: StructuredProductData, context: Dict[str, Any]) -> RuleCheckResult:
        """
        Executes deterministic legal compliance verification on the structured product declarations.
        Returns a structured RuleCheckResult.
        """
        pass

    def create_result(
        self,
        status: RuleStatus,
        extracted_value: Any,
        expected_requirement: str,
        explanation: str
    ) -> RuleCheckResult:
        """Helper to create standardized RuleCheckResult."""
        return RuleCheckResult(
            rule_id=self.rule_id,
            legal_reference=self.legal_reference,
            field_checked=self.field_checked,
            extracted_value=extracted_value,
            expected_requirement=expected_requirement,
            status=status,
            explanation=explanation
        )
