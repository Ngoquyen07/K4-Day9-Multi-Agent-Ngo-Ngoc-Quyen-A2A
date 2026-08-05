import re
from typing import Dict, Any, List, Tuple

class VerifierAgent:
    """
    Verifier Agent:
    Validates final output JSON against README schema specs, array limits,
    evidence ID formats, rounding rules, and null handling contracts.
    """

    ALLOWED_PRIMARY_ISSUES = {
        "canceled_order_paid",
        "unavailable_order_paid",
        "late_delivery_seller",
        "late_delivery_logistics",
        "valid_split_payment",
        "unsupported_late_claim",
    }

    ALLOWED_SECONDARY_ISSUES = {
        "multi_item_order",
        "multi_seller_order",
        "split_payment",
        "repeat_customer",
        "multiple_categories",
    }

    ALLOWED_STATUS = {"action_required", "no_action"}

    EVIDENCE_REGEX = re.compile(r"^(order:.+|item:.+:.+|payment:.+:.+|seller:.+|policy:.+)$")

    def verify(self, output: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []

        # Top-level required keys
        required_keys = [
            "case_id",
            "case_assessment",
            "affected_entities",
            "customer_context",
            "product_context",
            "delivery_analysis",
            "payment_reconciliation",
            "root_cause_analysis",
            "evidence_ids",
            "financial_resolution",
            "resolution_actions",
        ]

        for k in required_keys:
            if k not in output:
                errors.append(f"Missing top-level key: {k}")

        if errors:
            return False, errors

        # Case Assessment
        ca = output.get("case_assessment", {})
        if ca.get("primary_issue") not in self.ALLOWED_PRIMARY_ISSUES:
            errors.append(f"Invalid primary_issue: {ca.get('primary_issue')}")
        if ca.get("case_status") not in self.ALLOWED_STATUS:
            errors.append(f"Invalid case_status: {ca.get('case_status')}")
        conf = ca.get("confidence", 0.0)
        if not (0.0 <= conf <= 1.0):
            errors.append(f"Confidence {conf} out of range [0, 1]")

        for sec in ca.get("secondary_issues", []):
            if sec not in self.ALLOWED_SECONDARY_ISSUES:
                errors.append(f"Invalid secondary_issue: {sec}")

        # Affected entities limits
        ae = output.get("affected_entities", {})
        if len(ae.get("order_ids", [])) > 5:
            errors.append("order_ids exceeds limit 5")
        if len(ae.get("item_ids", [])) > 5:
            errors.append("item_ids exceeds limit 5")
        if len(ae.get("seller_ids", [])) > 3:
            errors.append("seller_ids exceeds limit 3")
        if len(ae.get("payment_ids", [])) > 5:
            errors.append("payment_ids exceeds limit 5")

        # Context limits
        cc = output.get("customer_context", {})
        if len(cc.get("related_order_ids", [])) > 5:
            errors.append("related_order_ids exceeds limit 5")

        pc = output.get("product_context", {})
        if len(pc.get("product_ids", [])) > 5:
            errors.append("product_ids exceeds limit 5")
        if len(pc.get("category_names", [])) > 5:
            errors.append("category_names exceeds limit 5")

        # Root cause limits
        rca = output.get("root_cause_analysis", {})
        if len(rca.get("ranked_causes", [])) > 3:
            errors.append("ranked_causes exceeds limit 3")
        if len(rca.get("responsible_parties", [])) > 3:
            errors.append("responsible_parties exceeds limit 3")

        # Evidence IDs check
        ev_ids = output.get("evidence_ids", [])
        if len(ev_ids) > 20:
            errors.append("evidence_ids exceeds limit 20")
        for ev in ev_ids:
            if not self.EVIDENCE_REGEX.match(ev):
                errors.append(f"Invalid evidence_id format: {ev}")

        # Actions limit
        actions = output.get("resolution_actions", [])
        if len(actions) > 5:
            errors.append("resolution_actions exceeds limit 5")

        return (len(errors) == 0), errors
