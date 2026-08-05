import os
import json
import zipfile
from tqdm import tqdm
from src.data_loader import OlistDataLoader
from src.tracer import ExecutionTracer
from src.agents.coordinator_agent import CoordinatorAgent

def ensure_directories():
    os.makedirs("input", exist_ok=True)
    os.makedirs("output", exist_ok=True)

def generate_sample_inputs_if_empty(loader: OlistDataLoader, count: int = 50):
    """
    If input/ directory is empty, populates 50 benchmark input files.
    """
    existing_inputs = [f for f in os.listdir("input") if f.startswith("EC_") and f.endswith(".json")]
    if len(existing_inputs) >= count:
        print(f"Found {len(existing_inputs)} input files in input/.")
        return

    print(f"Generating {count} sample benchmark input files in input/...")
    order_ids = list(loader.orders.keys())[:count]

    for i, oid in enumerate(order_ids, start=1):
        case_id = f"EC_{i:03d}"
        case_data = {
            "case_id": case_id,
            "customer_request": {
                "language": "vi",
                "message": "Hãy điều tra khiếu nại, kiểm tra lịch sử khách hàng và đối soát toàn bộ order.",
                "claimed_order_id": oid,
            },
            "investigation_scope": {
                "include_customer_history": True,
                "include_product_context": True,
            },
            "policy_version": "EC_POLICY_V2",
        }
        with open(os.path.join("input", f"{case_id}.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(case_data, indent=2, ensure_ascii=False))

    print("Sample inputs generated successfully.")

def run_pipeline():
    ensure_directories()
    
    print("Initializing Olist Data Loader...")
    loader = OlistDataLoader(data_dir="data")
    
    # Generate input cases if empty
    generate_sample_inputs_if_empty(loader, count=50)

    tracer = ExecutionTracer(trace_file="trace.jsonl")
    tracer.clear()

    coordinator = CoordinatorAgent(loader, tracer, verbose=False, use_llm=False)

    input_files = sorted([f for f in os.listdir("input") if f.startswith("EC_") and f.endswith(".json")])
    print(f"Processing {len(input_files)} cases...")

    output_files_created = []

    for fname in tqdm(input_files, desc="Processing Cases"):
        input_path = os.path.join("input", fname)
        output_path = os.path.join("output", fname)

        with open(input_path, "r", encoding="utf-8") as f:
            case_input = json.load(f)

        output_data = coordinator.process_case(case_input)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(output_data, indent=2, ensure_ascii=False))

        output_files_created.append(output_path)

    print(f"Successfully processed {len(output_files_created)} cases into output/")

    # Zip 50 output files directly at root of output.zip per README Section 8 standard
    zip_filename = "output.zip"
    print(f"Creating {zip_filename} containing exact 50 JSON files at root...")
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for out_file in output_files_created:
            zipf.write(out_file, arcname=os.path.basename(out_file))

    print(f"File {zip_filename} created containing {len(output_files_created)} JSON files at zip root.")

if __name__ == "__main__":
    run_pipeline()
