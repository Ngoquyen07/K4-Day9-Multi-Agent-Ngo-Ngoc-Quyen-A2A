"""LLM-driven multi-agent pipeline for EC_POLICY_V2 dispute investigations."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
INPUT = next((path for path in (ROOT / "input", ROOT / "input" / "input") if any(path.glob("EC_*.json"))), ROOT / "input")
OUTPUT = ROOT / "output"
TRACE = ROOT / "trace.jsonl"
MODEL_NAME = "meta-llama/llama-3.1-8b-instruct"
BASE_URL = "https://openrouter.ai/api/v1"

POLICY = """
Apply EC_POLICY_V2 in priority order: (1) canceled_order_paid when canceled and payment total > 0: platform OLIST_PLATFORM, full payment refund, issue_full_refund, ORDER_CANCELED_AFTER_PAYMENT; (2) unavailable_order_paid analogously with ORDER_UNAVAILABLE_AFTER_PAYMENT; (3) late_delivery_seller when delivered after estimate and a seller carrier handoff is after that seller's earliest shipping limit: late sellers, total freight refund, refund_freight, SELLER_HANDOFF_AFTER_LIMIT; (4) late_delivery_logistics when delivered after estimate with no late seller: LOGISTICS_PROVIDER, total freight refund, refund_freight, CARRIER_DELIVERED_AFTER_ESTIMATE; (5) valid_split_payment when at least two payment rows and abs(payment total - item price total - freight total) <= 0.10: zero refund, explain_valid_split_payment, MULTIPLE_PAYMENTS_RECONCILED; (6) unsupported_late_claim when not delivered late and payment reconciles: zero refund, reject_late_refund, DELIVERY_WITHIN_ESTIMATE. Secondary issues in this exact order: multi_item_order (2+ item rows), multi_seller_order (2+ distinct sellers), split_payment (2+ payment rows), repeat_customer (related order exists), multiple_categories (2+ categories). Actions: primary first, then review_seller_handoff or review_carrier_delay when applicable, verify_refund_completion for a refund, coordinate_multi_seller_case for multiple sellers, verify_payment_allocation for split payment except valid_split_payment. Round money and hours to two decimals. For no items, item/freight/expected/difference/reconciled are null and item/seller/product/category/handoff arrays are empty.
""".strip()

OUTPUT_SCHEMA = {
    "case_id": "EC_001",
    "case_assessment": {"primary_issue": "...", "secondary_issues": [], "case_status": "action_required|no_action", "confidence": 0.95},
    "affected_entities": {"order_ids": [], "item_ids": [], "seller_ids": [], "payment_ids": []},
    "customer_context": {"customer_unique_id": "...", "related_order_ids": []},
    "product_context": {"product_ids": [], "category_names": []},
    "delivery_analysis": {"delivered_at": None, "estimated_delivery_at": None, "carrier_handoff_at": None, "delivery_variance_hours": None, "seller_handoff_analysis": [], "late_handoff_seller_ids": []},
    "payment_reconciliation": {"currency": "BRL", "item_total_brl": None, "freight_total_brl": None, "expected_total_brl": None, "payment_total_brl": 0.0, "difference_brl": None, "reconciled": None, "payment_types": []},
    "root_cause_analysis": {"ranked_causes": [], "responsible_parties": []},
    "evidence_ids": [],
    "financial_resolution": {"currency": "BRL", "recommended_refund_brl": 0.0},
    "resolution_actions": [],
}


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    return None if value is None or pd.isna(value) else value


def grouped(frame: pd.DataFrame, key: str) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in frame.to_dict("records"):
        result[str(row[key])].append(clean(row))
    return result


class OlistData:
    """Indexes source facts only; it makes no business decision."""

    def __init__(self) -> None:
        read = lambda name: pd.read_csv(DATA / name)
        orders = read("olist_orders_dataset.csv")
        customers = read("olist_customers_dataset.csv")
        self.orders = {str(row["order_id"]): clean(row) for row in orders.to_dict("records")}
        self.customers = {str(row["customer_id"]): clean(row) for row in customers.to_dict("records")}
        self.items = grouped(read("olist_order_items_dataset.csv"), "order_id")
        self.payments = grouped(read("olist_order_payments_dataset.csv"), "order_id")
        self.products = {str(row["product_id"]): clean(row) for row in read("olist_products_dataset.csv").to_dict("records")}
        translation = read("product_category_name_translation.csv")
        self.category_names = {
            row["product_category_name"]: row["product_category_name_english"]
            for row in translation.to_dict("records")
        }
        self.orders_by_customer_unique: dict[str, list[str]] = defaultdict(list)
        for row in orders.to_dict("records"):
            customer = self.customers[str(row["customer_id"])]
            self.orders_by_customer_unique[str(customer["customer_unique_id"])].append(str(row["order_id"]))

    def evidence(self, case: dict[str, Any]) -> dict[str, Any]:
        order_id = case["customer_request"]["claimed_order_id"]
        order = self.orders.get(order_id)
        if not order:
            raise ValueError(f"Unknown claimed_order_id: {order_id}")
        customer = self.customers[str(order["customer_id"])]
        product_rows = []
        for item in self.items.get(order_id, []):
            product = self.products.get(str(item["product_id"]), {})
            category = product.get("product_category_name")
            product_rows.append({"product_id": item["product_id"], "category_name": self.category_names.get(category, category)})
        customer_unique_id = str(customer["customer_unique_id"])
        related = [candidate for candidate in self.orders_by_customer_unique[customer_unique_id] if candidate != order_id][:5]
        return {
            "case": case,
            "order": order,
            "customer": {"customer_unique_id": customer_unique_id, "related_order_ids": related},
            "items": self.items.get(order_id, []),
            "products": product_rows,
            "payments": self.payments.get(order_id, []),
        }


class LLM:
    def __init__(self) -> None:
        load_dotenv(ROOT / ".env")
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured in .env")
        self.client = OpenAI(base_url=BASE_URL, api_key=api_key, timeout=60, max_retries=0)

    def json(self, agent: str, instruction: str, payload: dict[str, Any], max_tokens: int = 1200) -> dict[str, Any]:
        prompt = f"""You are the {agent} in a multi-agent Olist dispute system. {instruction}

Return one valid JSON object only: no markdown, no prose, no invented IDs or timestamps. Source facts follow.
{json.dumps(payload, ensure_ascii=False, default=str)}"""
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": "Use only supplied evidence. Output valid JSON only."},
                        {"role": "user", "content": prompt + ("\nYour prior response was invalid or truncated. Return only the complete JSON object, with no commentary." if attempt else "")},
                    ],
                    temperature=0,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or ""
                return json.loads(content.strip().removeprefix("```json").removesuffix("```").strip())
            except Exception as error:
                last_error = error
                time.sleep(2)
        raise RuntimeError(f"{agent} did not return valid JSON after 3 attempts: {last_error}")


def check_schema(output: dict[str, Any]) -> list[str]:
    errors = []
    if set(output) != set(OUTPUT_SCHEMA):
        errors.append("top-level schema mismatch")
    if not isinstance(output.get("case_assessment", {}).get("confidence"), (int, float)):
        errors.append("confidence must be numeric")
    elif not 0 <= output["case_assessment"]["confidence"] <= 1:
        errors.append("confidence outside [0,1]")
    limits = {
        ("affected_entities", "order_ids"): 5, ("affected_entities", "item_ids"): 5,
        ("affected_entities", "seller_ids"): 3, ("affected_entities", "payment_ids"): 5,
        ("customer_context", "related_order_ids"): 5, ("product_context", "product_ids"): 5,
        ("product_context", "category_names"): 5, ("root_cause_analysis", "ranked_causes"): 3,
        ("root_cause_analysis", "responsible_parties"): 3,
    }
    for (section, key), maximum in limits.items():
        if not isinstance(output.get(section, {}).get(key), list) or len(output[section][key]) > maximum:
            errors.append(f"{section}.{key} limit")
    if len(output.get("evidence_ids", [])) > 20 or len(output.get("resolution_actions", [])) > 5:
        errors.append("evidence or action limit")
    return errors


def investigate(llm: LLM, data: OlistData, case: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    raw_evidence = data.evidence(case)
    handoff = llm.json(
        "Evidence Agent",
        "Analyze the supplied records without deciding liability. Return exactly these four short fields: customer_observation, order_observation, payment_observation, delivery_observation. Each value is a concise source-grounded string.",
        raw_evidence,
        max_tokens=2000,
    )
    draft = llm.json(
        "Policy Agent",
        f"{POLICY}\nReturn the complete final output using exactly this schema: {json.dumps(OUTPUT_SCHEMA)}. Use the Evidence Agent handoff as the analysis, preserving source order and IDs. Include no fields outside the schema and keep strings to source IDs, timestamps, category names, party IDs, issue codes, and action codes only.",
        {"case": case, "raw_evidence": raw_evidence, "evidence_handoff": handoff},
        max_tokens=3500,
    )
    errors = check_schema(draft)
    if errors:
        draft = llm.json(
            "Verifier Agent",
            f"Validate and correct the Policy Agent draft against this required schema: {json.dumps(OUTPUT_SCHEMA)}. Keep the policy decision evidence-grounded. Return the corrected final JSON only. Local structural errors found: {errors}",
            {"raw_evidence": raw_evidence, "draft": draft, "policy": POLICY},
            max_tokens=3500,
        )
        errors = check_schema(draft)
    if errors:
        raise RuntimeError(f"Verifier Agent returned invalid output for {case['case_id']}: {errors}")
    return draft, [
        {"agent": "Coordinator Agent", "status": "dispatched"},
        {"agent": "Evidence Agent", "status": "handoff_completed"},
        {"agent": "Policy Agent", "status": "draft_completed"},
        {"agent": "Verifier Agent", "status": "passed"},
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", help="Run one EC case for a live LLM smoke test")
    args = parser.parse_args()
    cases = sorted(INPUT.glob("EC_*.json"))
    if not args.case and len(cases) != 50:
        raise ValueError(f"Expected 50 input cases in {INPUT}, found {len(cases)}")
    if args.case:
        cases = [INPUT / f"{args.case}.json"]
    llm, data = LLM(), OlistData()
    OUTPUT.mkdir(exist_ok=True)
    traces: list[str] = []
    for path in cases:
        case = json.loads(path.read_text(encoding="utf-8"))
        output, events = investigate(llm, data, case)
        (OUTPUT / path.name).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        traces.extend(json.dumps({"case_id": case["case_id"], **event}) for event in events)
        print(f"Completed {case['case_id']} with LLM agents.")
    if not args.case:
        TRACE.write_text("\n".join(traces) + "\n", encoding="utf-8")
        shutil.make_archive(str(ROOT / "output"), "zip", OUTPUT)
    print(f"Model: {MODEL_NAME}")


if __name__ == "__main__":
    main()
