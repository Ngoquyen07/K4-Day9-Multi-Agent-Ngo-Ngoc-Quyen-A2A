import json
import os
from typing import Dict, Any

class ExecutionTracer:
    """
    Tracer for recording agent execution trajectories into trace.jsonl.
    Appends execution steps for each case.
    """

    def __init__(self, trace_file: str = "trace.jsonl"):
        self.trace_file = trace_file

    def clear(self):
        """Clears trace file for fresh run."""
        if os.path.exists(self.trace_file):
            os.remove(self.trace_file)

    def log_step(self, case_id: str, agent_name: str, step_type: str, details: Dict[str, Any]):
        record = {
            "case_id": case_id,
            "agent": agent_name,
            "step_type": step_type,
            "details": details,
        }
        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
