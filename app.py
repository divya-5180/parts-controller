import json
import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from state import BatchLedger
from llm_client import ResilientLLMClient
from controller import PartsController

app = FastAPI(title="Parts Request Controller API", version="1.0.0")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State Management
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOGUE_PATH = os.path.join(BASE_DIR, "sample_data", "catalogue.json")

def load_catalogue() -> Dict[str, Any]:
    if os.path.exists(CATALOGUE_PATH):
        with open(CATALOGUE_PATH, "r") as f:
            return json.load(f)
    return {}

def save_catalogue(data: Dict[str, Any]):
    os.makedirs(os.path.dirname(CATALOGUE_PATH), exist_ok=True)
    with open(CATALOGUE_PATH, "w") as f:
        json.dump(data, f, indent=2)

# Global System Engine
catalogue_db = load_catalogue()
ledger = BatchLedger(initial_budget=100.0, low_budget_threshold=15.0)
llm_client = ResilientLLMClient()
controller = PartsController(catalogue_db, ledger, llm_client)

# Pydantic Schemas
class SingleRequestInput(BaseModel):
    request_id: str
    prompt: str

class CatalogueItemInput(BaseModel):
    part_id: str
    voltage_v: float
    connector_type: str
    max_power_w: float
    stock_count: int

# API Routes
@app.get("/api/summary")
def get_summary():
    """Returns batch ledger metrics and complete evidence logs."""
    return {
        "summary": ledger.export_summary(),
        "evidence": {req_id: log.to_dict() for req_id, log in ledger.evidence.items()}
    }

@app.get("/api/catalogue")
def get_catalogue():
    """Returns the current parts catalogue."""
    return load_catalogue()

@app.post("/api/catalogue")
def update_catalogue_item(item: CatalogueItemInput):
    """Add or update an item in the catalogue database."""
    cat = load_catalogue()
    cat[item.part_id] = {
        "voltage_v": item.voltage_v,
        "connector_type": item.connector_type,
        "max_power_w": item.max_power_w,
        "stock_count": item.stock_count
    }
    save_catalogue(cat)
    # Refresh controller catalogue reference
    controller.catalogue = cat
    controller.tools.catalogue_db = cat
    return {"message": f"Part {item.part_id} updated successfully", "catalogue": cat}

@app.post("/api/process/single")
def process_single_request(req: SingleRequestInput):
    """Processes a single incoming parts request in real time."""
    req_dict = [{"request_id": req.request_id, "prompt": req.prompt}]
    results = controller.process_batch(req_dict)
    log = ledger.evidence.get(req.request_id)
    return {
        "result": results[0],
        "evidence": log.to_dict() if log else None,
        "summary": ledger.export_summary()
    }

@app.post("/api/process/batch")
def process_batch_requests(requests: List[SingleRequestInput]):
    """Processes a batch array of parts requests."""
    req_dicts = [{"request_id": r.request_id, "prompt": r.prompt} for r in requests]
    results = controller.process_batch(req_dicts)
    return {
        "results": results,
        "summary": ledger.export_summary()
    }

@app.post("/api/reset")
def reset_ledger(budget: Optional[float] = 100.0):
    """Resets the spending ledger and clears evidence history."""
    global ledger, controller
    ledger = BatchLedger(initial_budget=budget, low_budget_threshold=15.0)
    controller.ledger = ledger
    controller.tools.ledger = ledger
    return {"message": "Ledger reset successfully", "summary": ledger.export_summary()}

# Mount Static Frontend
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.get("/")
def read_root():
    """Serves the primary web dashboard interface."""
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))

