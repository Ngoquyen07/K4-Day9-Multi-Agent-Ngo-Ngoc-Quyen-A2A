from typing import Dict, Any, List, Tuple

class VerifierAgent:
    """
    Verifier Agent:
    Validates output JSON schema against cohort rules and array limits.
    """

    def __init__(self):
        self.allowed_primary_issues = {
            "canceled_order_paid",
            "unavailable_order_paid",
            "late_delivery_seller",
            "late_delivery_logistics",
            "valid_split_payment",
            "unsupported_late_claim",
        }

    def verify(self, output: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []

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
                errors.append(f"Missing top-level key: '{k}'")

        if errors:
            return False, errors

        # Case Assessment
        ca = output.get("case_assessment", {})
        primary = ca.get("primary_issue")
        if primary not in self.allowed_primary_issues:
            errors.append(f"Unknown primary_issue: '{primary}'")

        # Financial Resolution vs Case Status
        fr = output.get("financial_resolution", {})
        refund = fr.get("recommended_refund_brl", 0.0)
        status = ca.get("case_status")
        if refund > 0 and status != "action_required":
            errors.append(f"Refund is {refund} > 0 but case_status is '{status}'")
        if refund == 0 and status != "no_action":
            errors.append(f"Refund is 0.0 but case_status is '{status}'")

        # Array Limits
        if len(output.get("resolution_actions", [])) > 5:
            errors.append(f"resolution_actions length {len(output.get('resolution_actions', []))} exceeds limit 5")

        if len(output.get("evidence_ids", [])) > 20:
            errors.append(f"evidence_ids length {len(output.get('evidence_ids', []))} exceeds limit 20")

        return (len(errors) == 0), errors
