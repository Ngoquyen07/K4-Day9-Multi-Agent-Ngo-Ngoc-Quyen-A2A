import os
import sys
import json
import re
from typing import Dict, Any, List, Tuple
from src.data_loader import OlistDataLoader

# Ensure stdout handles UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

class CohortValidator:
    """
    Validator for cohort submission requirements:
    1. Quantity: Exactly 50 JSON files in output/
    2. Schema: Fully parseable JSON matching cohort schema
    3. Grounding: All Evidence IDs exist directly in source CSV data
    4. Policy: Decision, refund, and actions match policy version (EC_POLICY_V2 / V1)
    5. Handoff: Execution trace log present in trace.jsonl
    """

    def __init__(self, data_loader: OlistDataLoader):
        self.loader = data_loader

        self.allowed_primary_issues = {
            "canceled_order_paid",
            "unavailable_order_paid",
            "late_delivery_seller",
            "late_delivery_logistics",
            "valid_split_payment",
            "unsupported_late_claim",
        }

        self.allowed_root_causes = {
            "SELLER_HANDOFF_AFTER_LIMIT",
            "CARRIER_DELIVERED_AFTER_ESTIMATE",
            "ORDER_CANCELED_AFTER_PAYMENT",
            "ORDER_UNAVAILABLE_AFTER_PAYMENT",
            "MULTIPLE_PAYMENTS_RECONCILED",
            "DELIVERY_WITHIN_ESTIMATE",
        }

    def _log(self, text: str):
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode("ascii", errors="replace").decode("ascii"))

    def validate_ticket(self, case_input: Dict[str, Any], output: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        case_id = output.get("case_id", "")
        claimed_order_id = case_input.get("customer_request", {}).get("claimed_order_id", "")

        # 1. Top level keys
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
                errors.append(f"[{case_id}] Missing top-level key: {k}")

        if errors:
            return False, errors

        # 2. Check Order Existence
        order = self.loader.get_order(claimed_order_id)
        if not order:
            errors.append(f"[{case_id}] Claimed order {claimed_order_id} does not exist in dataset")

        # 3. Grounding Check: Evidence IDs
        ev_ids = output.get("evidence_ids", [])
        if len(ev_ids) > 20:
            errors.append(f"[{case_id}] Evidence IDs count {len(ev_ids)} exceeds limit 20")

        for ev in ev_ids:
            if ev.startswith("order:"):
                oid = ev.split("order:")[1]
                if not self.loader.get_order(oid):
                    errors.append(f"[{case_id}] Evidence Grounding Error: Order ID '{oid}' in evidence '{ev}' not found in source CSV")
            elif ev.startswith("item:"):
                parts = ev.split("item:")[1].split(":")
                if len(parts) >= 2:
                    oid, item_seq = parts[0], int(parts[1])
                    items = self.loader.get_order_items(oid)
                    found = any(i["order_item_id"] == item_seq for i in items)
                    if not found:
                        errors.append(f"[{case_id}] Evidence Grounding Error: Item '{ev}' not found in source CSV for order {oid}")
            elif ev.startswith("payment:"):
                parts = ev.split("payment:")[1].split(":")
                if len(parts) >= 2:
                    oid, pay_seq = parts[0], int(parts[1])
                    payments = self.loader.get_order_payments(oid)
                    found = any(p["payment_sequential"] == pay_seq for p in payments)
                    if not found:
                        errors.append(f"[{case_id}] Evidence Grounding Error: Payment '{ev}' not found in source CSV for order {oid}")
            elif ev.startswith("seller:"):
                sid = ev.split("seller:")[1]
                if not self.loader.get_seller(sid):
                    errors.append(f"[{case_id}] Evidence Grounding Error: Seller ID '{sid}' in evidence '{ev}' not found in source CSV")
            elif ev.startswith("policy:"):
                code = ev.split("policy:")[1]
                if code not in self.allowed_root_causes:
                    errors.append(f"[{case_id}] Evidence Policy Error: Unknown policy root cause code '{code}'")
            else:
                errors.append(f"[{case_id}] Invalid evidence_id prefix: '{ev}'")

        # 4. Policy Check
        ca = output.get("case_assessment", {})
        primary = ca.get("primary_issue")
        if primary not in self.allowed_primary_issues:
            errors.append(f"[{case_id}] Unknown primary_issue: '{primary}'")

        fr = output.get("financial_resolution", {})
        refund = fr.get("recommended_refund_brl", 0.0)
        status = ca.get("case_status")
        if refund > 0 and status != "action_required":
            errors.append(f"[{case_id}] Policy Mismatch: Refund is {refund} BRL > 0 but case_status is '{status}' instead of 'action_required'")
        if refund == 0 and status != "no_action":
            errors.append(f"[{case_id}] Policy Mismatch: Refund is 0.0 BRL but case_status is '{status}' instead of 'no_action'")

        # 5. Null Handling Check for No-Item Orders
        items = self.loader.get_order_items(claimed_order_id)
        pr = output.get("payment_reconciliation", {})
        if len(items) == 0:
            if pr.get("expected_total_brl") is not None:
                errors.append(f"[{case_id}] Null Handling Error: No-item order expected_total_brl must be null")
            if pr.get("difference_brl") is not None:
                errors.append(f"[{case_id}] Null Handling Error: No-item order difference_brl must be null")
            if pr.get("reconciled") is not None:
                errors.append(f"[{case_id}] Null Handling Error: No-item order reconciled must be null")

        return (len(errors) == 0), errors

    def validate_all_50(self, input_dir: str = "input", output_dir: str = "output", trace_file: str = "trace.jsonl") -> bool:
        self._log("\n==========================================================================================")
        self._log("[VALIDATOR] RUNNING COHORT VALIDATOR SUITE ON ALL 50 TICKETS")
        self._log("==========================================================================================")

        # Check 1: Count
        out_files = sorted([f for f in os.listdir(output_dir) if f.startswith("EC_") and f.endswith(".json")])
        in_files = sorted([f for f in os.listdir(input_dir) if f.startswith("EC_") and f.endswith(".json")])

        self._log(f"[1. Ticket Count Check]: Input = {len(in_files)}, Output = {len(out_files)}")
        if len(out_files) != 50:
            self._log(f" [X] Ticket Count Error: Expected exactly 50 output files, found {len(out_files)}")
            return False
        self._log(" [OK] Ticket Count PASSED: Exactly 50 output JSON files present.")

        # Check 2: Trace file presence
        self._log("\n[2. Handoff Trace Log Check]:")
        if not os.path.exists(trace_file) or os.path.getsize(trace_file) == 0:
            self._log(f" [X] Handoff Trace Error: Trace file '{trace_file}' is missing or empty")
            return False
        self._log(f" [OK] Trace Log PASSED: '{trace_file}' ({os.path.getsize(trace_file)} bytes)")

        # Check 3, 4 & 5: Schema, Grounding & Policy for all 50
        self._log("\n[3, 4, 5. Schema, Evidence Grounding & Policy Check across 50 tickets]:")
        passed_count = 0
        all_errors = []

        for fname in out_files:
            in_path = os.path.join(input_dir, fname)
            out_path = os.path.join(output_dir, fname)

            with open(in_path, "r", encoding="utf-8") as f:
                case_in = json.load(f)
            with open(out_path, "r", encoding="utf-8") as f:
                case_out = json.load(f)

            is_valid, errs = self.validate_ticket(case_in, case_out)
            if is_valid:
                passed_count += 1
            else:
                all_errors.extend(errs)

        self._log(f" -> Result: {passed_count}/50 tickets passed all validation checks.")

        if all_errors:
            self._log("\n [X] Validation Errors Detected:")
            for err in all_errors[:10]:
                self._log(f"  - {err}")
            if len(all_errors) > 10:
                self._log(f"  ... and {len(all_errors) - 10} more errors.")
            return False

        self._log("\n==========================================================================================")
        self._log("[OK] ALL 50 TICKETS PASSED ALL COHORT VALIDATOR CHECKS PERFECTLY!")
        self._log("==========================================================================================\n")
        return True
