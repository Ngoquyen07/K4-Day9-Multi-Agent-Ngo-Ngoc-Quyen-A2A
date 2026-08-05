import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.data_loader import OlistDataLoader
from src.cohort_validator import CohortValidator

def main():
    loader = OlistDataLoader(data_dir="data")
    validator = CohortValidator(loader)
    success = validator.validate_all_50(input_dir="input", output_dir="output", trace_file="trace.jsonl")
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
