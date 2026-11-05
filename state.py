import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("PartsController.State")

@dataclass
class EvidenceLog:
    request_id: str
    raw_prompt: str
    extracted_reqs: Dict[str, Any] = field(default_factory=dict)
    candidate_ids: List[str] = field(default_factory=list)
    tools_called: List[Dict[str, Any]] = field(default_factory=list)
    passed_checks: List[str] = field(default_factory=list)
    failed_checks: List[str] = field(default_factory=list)
    action: str = "REFER"  # "DISPATCH" or "REFER"
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "raw_prompt": self.raw_prompt,
            "extracted_reqs": self.extracted_reqs,
            "candidate_ids": self.candidate_ids,
            "tools_called": self.tools_called,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "action": self.action,
            "reason": self.reason
        }

class BatchLedger:
    def __init__(self, initial_budget: float = 100.0, low_budget_threshold: float = 15.0):
        self.initial_budget = initial_budget
        self.remaining_budget = initial_budget
        self.total_units_spent = 0.0
        self.low_budget_threshold = low_budget_threshold
        self.evidence: Dict[str, EvidenceLog] = {}
        self.dispatched_count = 0
        self.referred_count = 0

    def is_low_budget(self) -> bool:
        return self.remaining_budget <= self.low_budget_threshold

    def record_spending(self, request_id: str, tool_name: str, cost: float, details: Optional[Dict[str, Any]] = None):
        self.remaining_budget -= cost
        self.total_units_spent += cost
        if request_id in self.evidence:
            self.evidence[request_id].tools_called.append({
                "tool": tool_name,
                "cost": cost,
                "details": details or {}
            })
        logger.info(f"Tool [{tool_name}] cost {cost} units. Remaining budget: {self.remaining_budget:.2f}")

    def record_decision(self, request_id: str, action: str, reason: str):
        if request_id in self.evidence:
            self.evidence[request_id].action = action
            self.evidence[request_id].reason = reason
            if action == "DISPATCH":
                self.dispatched_count += 1
            else:
                self.referred_count += 1

    def export_summary(self) -> Dict[str, Any]:
        return {
            "initial_budget": self.initial_budget,
            "total_units_spent": self.total_units_spent,
            "remaining_budget": self.remaining_budget,
            "dispatched": self.dispatched_count,
            "referred": self.referred_count,
            "total_requests": len(self.evidence)
        }