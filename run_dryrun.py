import json
import os
from state import BatchLedger
from llm_client import ResilientLLMClient
from controller import PartsController

def run():
    # Resolve exact paths to data files
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cat_path = os.path.join(base_dir, "sample_data", "catalogue.json")
    req_path = os.path.join(base_dir, "sample_data", "requests.json")

    # Load catalogue and sample requests
    with open(cat_path) as f:
        catalogue = json.load(f)
    with open(req_path) as f:
        requests = json.load(f)

    # Initialize tracking ledger, LLM client, and main controller
    ledger = BatchLedger(initial_budget=50.0, low_budget_threshold=10.0)
    llm_client = ResilientLLMClient()
    controller = PartsController(catalogue, ledger, llm_client)

    # Process all sample requests
    results = controller.process_batch(requests)

    # Save decisions to results.json
    output_path = os.path.join(base_dir, "results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    # Print summary of spending and decisions
    summary = ledger.export_summary()
    print("\n=== BATCH SUMMARY REPORT ===")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    run()