import json
import logging
from typing import Any, Dict, Optional
from state import BatchLedger

logger = logging.getLogger("PartsController.Tools")

TOOL_COSTS = {
    "inspection": 2.0,
    "clarification": 1.5,
    "stock_verification": 3.0
}

class ToolProtocol:
    def __init__(self, ledger: BatchLedger, catalogue_db: Optional[Dict[str, Any]] = None):
        self.ledger = ledger
        self.catalogue_db = catalogue_db or {}

    def inspect_part(self, request_id: str, part_id: str) -> Dict[str, Any]:
        """Looks up physical specifications for a specific part ID."""
        cost = TOOL_COSTS["inspection"]
        self.ledger.record_spending(request_id, "inspection", cost, {"part_id": part_id})
        
        part_info = self.catalogue_db.get(part_id)
        if not part_info:
            return {"success": False, "error": f"Part {part_id} not found in catalogue."}
        
        return {
            "success": True,
            "part_id": part_id,
            "voltage_v": part_info.get("voltage_v"),
            "connector_type": part_info.get("connector_type"),
            "max_power_w": part_info.get("max_power_w"),
            "max_current_a": part_info.get("max_current_a")
        }

    def clarify_request(self, request_id: str, missing_field: str) -> Dict[str, Any]:
        """Simulates/issues a clarification query to resolve missing requirements."""
        cost = TOOL_COSTS["clarification"]
        self.ledger.record_spending(request_id, "clarification", cost, {"missing_field": missing_field})
        
        # Simulates interactive response or tool return payload
        return {
            "success": True,
            "request_id": request_id,
            "clarification_provided": f"Simulated detail for {missing_field}"
        }

    def verify_stock(self, request_id: str, part_id: str, required_qty: int = 1) -> Dict[str, Any]:
        """Performs real-time stock lookup for a shortlisted part."""
        cost = TOOL_COSTS["stock_verification"]
        self.ledger.record_spending(request_id, "stock_verification", cost, {"part_id": part_id, "qty": required_qty})
        
        part_info = self.catalogue_db.get(part_id, {})
        actual_stock = part_info.get("stock_count", 0)
        is_in_stock = actual_stock >= required_qty
        
        return {
            "success": True,
            "part_id": part_id,
            "in_stock": is_in_stock,
            "available_quantity": actual_stock
        }