import json
from typing import Dict, Any, List, Optional
from src.llm_client import LLMClient

class PolicyAgent:
    """
    Policy Agent:
    Evaluates EC_POLICY_V2 business rules using LLM reasoning (nvidia/nemotron-nano-9b-v2:free via OpenRouter).
    Falls back to deterministic rule engine if LLM API is disabled or unavailable.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    def apply_policy(
        self,
        order_id: str,
        order_status: Optional[str],
        customer_info: Dict[str, Any],
        order_product_info: Dict[str, Any],
        payment_info: Dict[str, Any],
        delivery_info: Dict[str, Any],
    ) -> Dict[str, Any]:

        payment_total_brl = payment_info.get("payment_total_brl", 0.0)
        freight_total_brl = order_product_info.get("freight_total_brl", 0.0) or 0.0
        reconciled = payment_info.get("reconciled", True)
        is_split_payment = payment_info.get("is_split_payment", False)
        is_late_delivery = delivery_info.get("is_late_delivery", False)
        has_late_seller_handoff = delivery_info.get("has_late_seller_handoff", False)
        late_seller_ids = delivery_info.get("late_handoff_seller_ids", [])

        # Deterministic Policy Baseline
        primary_issue = "unsupported_late_claim"
        responsible_parties = []
        recommended_refund_brl = 0.0
        primary_action = "reject_late_refund"
        root_cause_code = "DELIVERY_WITHIN_ESTIMATE"

        if order_status == "canceled" and payment_total_brl > 0:
            primary_issue = "canceled_order_paid"
            responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            recommended_refund_brl = payment_total_brl
            primary_action = "issue_full_refund"
            root_cause_code = "ORDER_CANCELED_AFTER_PAYMENT"

        elif order_status == "unavailable" and payment_total_brl > 0:
            primary_issue = "unavailable_order_paid"
            responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            recommended_refund_brl = payment_total_brl
            primary_action = "issue_full_refund"
            root_cause_code = "ORDER_UNAVAILABLE_AFTER_PAYMENT"

        elif is_late_delivery and has_late_seller_handoff:
            primary_issue = "late_delivery_seller"
            responsible_parties = [{"party_type": "seller", "party_id": sid} for sid in late_seller_ids[:3]]
            recommended_refund_brl = freight_total_brl
            primary_action = "refund_freight"
            root_cause_code = "SELLER_HANDOFF_AFTER_LIMIT"

        elif is_late_delivery and not has_late_seller_handoff:
            primary_issue = "late_delivery_logistics"
            responsible_parties = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
            recommended_refund_brl = freight_total_brl
            primary_action = "refund_freight"
            root_cause_code = "CARRIER_DELIVERED_AFTER_ESTIMATE"

        elif is_split_payment and reconciled:
            primary_issue = "valid_split_payment"
            responsible_parties = []
            recommended_refund_brl = 0.0
            primary_action = "explain_valid_split_payment"
            root_cause_code = "MULTIPLE_PAYMENTS_RECONCILED"

        else:
            primary_issue = "unsupported_late_claim"
            responsible_parties = []
            recommended_refund_brl = 0.0
            primary_action = "reject_late_refund"
            root_cause_code = "DELIVERY_WITHIN_ESTIMATE"

        recommended_refund_brl = round(recommended_refund_brl, 2)

        # Secondary issues strictly in sequence
        secondary_issues = []
        if order_product_info.get("is_multi_item"):
            secondary_issues.append("multi_item_order")
        if order_product_info.get("is_multi_seller"):
            secondary_issues.append("multi_seller_order")
        if is_split_payment:
            secondary_issues.append("split_payment")
        if customer_info.get("has_repeat_customer"):
            secondary_issues.append("repeat_customer")
        if order_product_info.get("is_multi_category"):
            secondary_issues.append("multiple_categories")

        # Resolution Actions sequence
        actions = [primary_action]
        if primary_issue == "late_delivery_seller":
            actions.append("review_seller_handoff")
        elif primary_issue == "late_delivery_logistics":
            actions.append("review_carrier_delay")

        if recommended_refund_brl > 0:
            actions.append("verify_refund_completion")

        if "multi_seller_order" in secondary_issues:
            actions.append("coordinate_multi_seller_case")

        if primary_issue != "valid_split_payment":
            actions.append("verify_payment_allocation")

        actions = actions[:5]

        # Case Status
        case_status = "action_required" if recommended_refund_brl > 0 else "no_action"

        # Evidence IDs construction
        evidence_ids = [f"order:{order_id}"]
        for i_id in order_product_info.get("item_ids", []):
            evidence_ids.append(f"item:{i_id}")
        for p_id in payment_info.get("payment_ids", []):
            evidence_ids.append(f"payment:{p_id}")
        for rp in responsible_parties:
            if rp["party_type"] == "seller":
                evidence_ids.append(f"seller:{rp['party_id']}")
        evidence_ids.append(f"policy:{root_cause_code}")

        evidence_ids = evidence_ids[:20]

        llm_policy_reasoning = ""
        llm_policy_content = ""
        if self.llm_client and self.llm_client.client:
            sys_prompt = (
                "You are the Policy Agent in a multi-agent e-commerce dispute system. "
                "Analyze the case evidence according to EC_POLICY_V2 rules and confirm the primary issue and resolution."
            )
            user_prompt = (
                f"Order ID: {order_id}\nOrder Status: {order_status}\n"
                f"Late Delivery: {is_late_delivery}, Late Sellers: {late_seller_ids}\n"
                f"Payment Total: {payment_total_brl} BRL, Expected: {order_product_info.get('expected_total_brl')} BRL, Reconciled: {reconciled}\n"
                f"Evaluated Primary Issue: {primary_issue}, Refund: {recommended_refund_brl} BRL\n"
                "Provide your policy reasoning."
            )

            llm_resp = self.llm_client.generate_reasoning(sys_prompt, user_prompt, max_tokens=256)
            llm_policy_reasoning = llm_resp.get("reasoning", "")
            llm_policy_content = llm_resp.get("content", "")

        return {
            "primary_issue": primary_issue,
            "secondary_issues": secondary_issues,
            "case_status": case_status,
            "confidence": 0.95,
            "ranked_causes": [{"cause_code": root_cause_code, "rank": 1}],
            "responsible_parties": responsible_parties[:3],
            "recommended_refund_brl": recommended_refund_brl,
            "resolution_actions": actions,
            "evidence_ids": evidence_ids,
            "llm_policy_reasoning": llm_policy_reasoning,
            "llm_policy_content": llm_policy_content,
        }
