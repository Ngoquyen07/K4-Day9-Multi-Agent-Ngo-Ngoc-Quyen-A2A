import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_loader import OlistDataLoader
from src.tracer import ExecutionTracer
from src.agents.coordinator_agent import CoordinatorAgent

def test_multi_agent_pipeline():
    print("Testing Multi-Agent Pipeline end-to-end...")
    loader = OlistDataLoader(data_dir="data")
    tracer = ExecutionTracer(trace_file="test_trace.jsonl")
    tracer.clear()

    coordinator = CoordinatorAgent(loader, tracer)

    # Pick sample order ID from loader
    sample_order_id = next(iter(loader.orders.keys()))
    case_input = {
        "case_id": "EC_TEST_001",
        "customer_request": {
            "language": "vi",
            "message": "Hãy điều tra khiếu nại.",
            "claimed_order_id": sample_order_id,
        },
        "investigation_scope": {
            "include_customer_history": True,
            "include_product_context": True,
        },
        "policy_version": "EC_POLICY_V2",
    }

    output = coordinator.process_case(case_input)
    print("\n--- Processed Case Output ---")
    print(json.dumps(output, indent=2, ensure_ascii=False))

    assert output["case_id"] == "EC_TEST_001"
    assert "primary_issue" in output["case_assessment"]
    assert "resolution_actions" in output
    assert "evidence_ids" in output
    print("\nMulti-Agent Pipeline Test PASSED!")

if __name__ == "__main__":
    test_multi_agent_pipeline()
