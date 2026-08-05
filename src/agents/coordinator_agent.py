import sys
import json
from typing import Dict, Any, Optional
from src.data_loader import OlistDataLoader
from src.llm_client import LLMClient
from src.agents.customer_agent import CustomerAgent
from src.agents.order_product_agent import OrderProductAgent
from src.agents.payment_agent import PaymentAgent
from src.agents.delivery_agent import DeliveryAgent
from src.agents.policy_agent import PolicyAgent
from src.agents.verifier_agent import VerifierAgent
from src.tracer import ExecutionTracer

# Ensure stdout handles UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

class CoordinatorAgent:
    """
    Coordinator / Supervisor Agent:
    Orchestrates execution flow across all sub-agents, aggregates results,
    invokes OpenRouter API (nvidia/nemotron-nano-9b-v2:free) for LLM reasoning,
    constructs standard output JSON schema, verifies contract compliance,
    and logs execution trace into trace.jsonl.
    """

    def __init__(self, data_loader: OlistDataLoader, tracer: ExecutionTracer, verbose: bool = True, use_llm: bool = True):
        self.data_loader = data_loader
        self.tracer = tracer
        self.verbose = verbose
        self.use_llm = use_llm

        self.llm_client = LLMClient(model_name="nvidia/nemotron-nano-9b-v2:free") if use_llm else None

        self.customer_agent = CustomerAgent(data_loader)
        self.order_product_agent = OrderProductAgent(data_loader)
        self.payment_agent = PaymentAgent(data_loader)
        self.delivery_agent = DeliveryAgent(data_loader)
        self.policy_agent = PolicyAgent(self.llm_client)
        self.verifier_agent = VerifierAgent()

    def _log(self, text: str):
        if self.verbose:
            try:
                print(text)
            except UnicodeEncodeError:
                print(text.encode("ascii", errors="replace").decode("ascii"))

    def process_case(self, case_input: Dict[str, Any]) -> Dict[str, Any]:
        case_id = case_input.get("case_id", "EC_000")
        cust_req = case_input.get("customer_request", {})
        claimed_order_id = cust_req.get("claimed_order_id", "")
        scope = case_input.get("investigation_scope", {})

        self.tracer.log_step(case_id, "CoordinatorAgent", "START_CASE", {"claimed_order_id": claimed_order_id})

        self._log("\n" + "=" * 90)
        self._log(f"[SUPERVISOR / COORDINATOR] Processing Case: {case_id} | Order ID: {claimed_order_id}")
        self._log("=" * 90)

        # 1. Fetch order header
        order = self.data_loader.get_order(claimed_order_id)
        order_status = order.get("order_status") if order else None
        self._log(f"  |-- [Order Header] Status='{order_status}' | Purchased='{order.get('order_purchase_timestamp') if order else 'N/A'}'")

        # 2. Customer Agent
        self._log("  |-- [CustomerAgent] Investigating customer identity & order history...")
        customer_res = self.customer_agent.analyze(claimed_order_id, scope)
        self.tracer.log_step(case_id, "CustomerAgent", "HANDOFF", customer_res)
        self._log(f"  |   |-- Reasoning: Customer Unique ID = '{customer_res['customer_unique_id']}'")
        self._log(f"  |   +-- Output: Related Orders Count = {len(customer_res['related_order_ids'])} | Repeat Customer = {customer_res['has_repeat_customer']}")

        # 3. Order & Product Agent
        self._log("  |-- [OrderProductAgent] Inspecting order items, products, sellers & categories...")
        op_res = self.order_product_agent.analyze(claimed_order_id, scope)
        self.tracer.log_step(case_id, "OrderProductAgent", "HANDOFF", {
            "item_count": len(op_res["items"]),
            "expected_total_brl": op_res["expected_total_brl"],
        })
        self._log(f"  |   |-- Reasoning: Items={len(op_res['items'])} | Sellers={op_res['seller_ids']} | Categories={op_res['category_names']}")
        self._log(f"  |   +-- Output: Item Total = {op_res['item_total_brl']} BRL, Freight Total = {op_res['freight_total_brl']} BRL -> Expected Total = {op_res['expected_total_brl']} BRL")

        # 4. Payment Agent
        self._log("  |-- [PaymentAgent] Reconciling payment transactions against expected total...")
        payment_res = self.payment_agent.analyze(claimed_order_id, op_res["expected_total_brl"])
        self.tracer.log_step(case_id, "PaymentAgent", "HANDOFF", {
            "payment_total_brl": payment_res["payment_total_brl"],
            "reconciled": payment_res["reconciled"],
        })
        self._log(f"  |   |-- Reasoning: Payment Rows={len(payment_res['payments'])} | Types={payment_res['payment_types']}")
        self._log(f"  |   +-- Output: Payment Total = {payment_res['payment_total_brl']} BRL | Reconciled = {payment_res['reconciled']} (Diff = {payment_res['difference_brl']} BRL)")

        # 5. Delivery Agent
        self._log("  |-- [DeliveryAgent] Analyzing delivery timestamps & seller handoff SLA...")
        delivery_res = self.delivery_agent.analyze(claimed_order_id, op_res["items"])
        self.tracer.log_step(case_id, "DeliveryAgent", "HANDOFF", {
            "delivery_variance_hours": delivery_res["delivery_variance_hours"],
            "late_sellers": delivery_res["late_handoff_seller_ids"],
        })
        self._log(f"  |   |-- Reasoning: Delivered='{delivery_res['delivered_at']}', Estimated='{delivery_res['estimated_delivery_at']}'")
        self._log(f"  |   +-- Output: Delivery Variance = {delivery_res['delivery_variance_hours']} hrs | Late Delivery = {delivery_res['is_late_delivery']} | Late Sellers = {delivery_res['late_handoff_seller_ids']}")

        # 6. Policy Agent
        self._log("  |-- [PolicyAgent] Evaluating EC_POLICY_V2 decision matrix with LLM reasoning...")
        policy_res = self.policy_agent.apply_policy(
            order_id=claimed_order_id,
            order_status=order_status,
            customer_info=customer_res,
            order_product_info=op_res,
            payment_info=payment_res,
            delivery_info=delivery_res,
        )
        self.tracer.log_step(case_id, "PolicyAgent", "HANDOFF", policy_res)

        # 7. Supervisor LLM Reasoning Call
        llm_reasoning_text = ""
        llm_content_text = ""
        if self.llm_client and self.llm_client.client:
            self._log("  |-- [Supervisor LLM API Call] Requesting reasoning from nvidia/nemotron-nano-9b-v2:free...")
            sys_prompt = "You are an expert e-commerce dispute supervisor. Analyze the handoff evidence and explain the primary issue, responsible party, and refund resolution concisely."
            user_prompt = f"Case ID: {case_id}\nOrder ID: {claimed_order_id}\nOrder Status: {order_status}\nExpected Total: {op_res['expected_total_brl']} BRL\nPayment Total: {payment_res['payment_total_brl']} BRL\nDelivery Variance: {delivery_res['delivery_variance_hours']} hours\nPrimary Issue: {policy_res['primary_issue']}\nRefund: {policy_res['recommended_refund_brl']} BRL"
            
            llm_resp = self.llm_client.generate_reasoning(sys_prompt, user_prompt, max_tokens=512)
            llm_reasoning_text = llm_resp["reasoning"]
            llm_content_text = llm_resp["content"]

            self.tracer.log_step(case_id, "SupervisorLLM", "API_RESPONSE", {
                "model": "nvidia/nemotron-nano-9b-v2:free",
                "reasoning": llm_reasoning_text,
                "content": llm_content_text,
            })
            if llm_reasoning_text:
                self._log(f"  |   |-- LLM CoT Reasoning: {llm_reasoning_text[:200]}...")
            if llm_content_text:
                self._log(f"  |   +-- LLM Synthesis: {llm_content_text[:200]}...")

        # Handle null values for no-item orders per README Section 4
        has_items = len(op_res["items"]) > 0
        item_total_brl = op_res["item_total_brl"] if has_items else None
        freight_total_brl = op_res["freight_total_brl"] if has_items else None
        expected_total_brl = op_res["expected_total_brl"] if has_items else None
        difference_brl = payment_res["difference_brl"] if has_items else None
        reconciled = payment_res["reconciled"] if has_items else None

        # 8. Construct final JSON Output matching README schema
        output = {
            "case_id": case_id,
            "case_assessment": {
                "primary_issue": policy_res["primary_issue"],
                "secondary_issues": policy_res["secondary_issues"],
                "case_status": policy_res["case_status"],
                "confidence": policy_res["confidence"],
            },
            "affected_entities": {
                "order_ids": [claimed_order_id],
                "item_ids": op_res["item_ids"],
                "seller_ids": op_res["seller_ids"],
                "payment_ids": payment_res["payment_ids"],
            },
            "customer_context": {
                "customer_unique_id": customer_res["customer_unique_id"] or "",
                "related_order_ids": customer_res["related_order_ids"],
            },
            "product_context": {
                "product_ids": op_res["product_ids"],
                "category_names": op_res["category_names"],
            },
            "delivery_analysis": {
                "delivered_at": delivery_res["delivered_at"],
                "estimated_delivery_at": delivery_res["estimated_delivery_at"],
                "carrier_handoff_at": delivery_res["carrier_handoff_at"],
                "delivery_variance_hours": delivery_res["delivery_variance_hours"],
                "seller_handoff_analysis": delivery_res["seller_handoff_analysis"],
                "late_handoff_seller_ids": delivery_res["late_handoff_seller_ids"],
            },
            "payment_reconciliation": {
                "currency": "BRL",
                "item_total_brl": item_total_brl,
                "freight_total_brl": freight_total_brl,
                "expected_total_brl": expected_total_brl,
                "payment_total_brl": payment_res["payment_total_brl"],
                "difference_brl": difference_brl,
                "reconciled": reconciled,
                "payment_types": payment_res["payment_types"],
            },
            "root_cause_analysis": {
                "ranked_causes": policy_res["ranked_causes"],
                "responsible_parties": policy_res["responsible_parties"],
            },
            "evidence_ids": policy_res["evidence_ids"],
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": policy_res["recommended_refund_brl"],
            },
            "resolution_actions": policy_res["resolution_actions"],
        }

        # 9. Verifier Agent
        self._log("  +-- [VerifierAgent] Verifying final schema & contract constraints...")
        is_valid, errors = self.verifier_agent.verify(output)
        if not is_valid:
            self.tracer.log_step(case_id, "VerifierAgent", "VERIFICATION_FAILED", {"errors": errors})
            self._log(f"      [X] VERIFICATION FAILED: {errors}")
        else:
            self.tracer.log_step(case_id, "VerifierAgent", "VERIFICATION_PASSED", {})
            self._log(f"      [OK] PASSED: Output schema and evidence contracts fully verified.")

        return output
