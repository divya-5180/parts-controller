import json
import logging
from typing import Any, Dict, List, Tuple
from state import BatchLedger, EvidenceLog
from tools import ToolProtocol
from llm_client import ResilientLLMClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PartsController.Main")

class DeterministicMatcher:
    @staticmethod
    def is_compatible(reqs: Dict[str, Any], part: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        Pure python rule checker.
        Rules:
        1. Voltage must match EXACTLY (tolerance 0.0V unless specified).
        2. Connector string normalized must match EXACTLY.
        3. Part max power (W) must be >= requested power (W). If current is given, derive W = V * A.
        """
        passed = []
        failed = []

        req_v = reqs.get("voltage_v")
        part_v = part.get("voltage_v")
        if req_v is not None and part_v is not None:
            if abs(float(req_v) - float(part_v)) < 1e-3:
                passed.append(f"Voltage match: {req_v}V")
            else:
                failed.append(f"Voltage mismatch: requested {req_v}V, part is {part_v}V")
        else:
            failed.append("Missing voltage parameter for evaluation")

        req_conn = str(reqs.get("connector_type") or "").strip().lower()
        part_conn = str(part.get("connector_type") or "").strip().lower()
        if req_conn and part_conn and req_conn == part_conn:
            passed.append(f"Connector match: {part_conn}")
        else:
            failed.append(f"Connector mismatch: requested '{req_conn}', part is '{part_conn}'")

        req_w = reqs.get("power_w")
        if req_w is None and reqs.get("current_a") is not None and req_v is not None:
            req_w = float(reqs["current_a"]) * float(req_v)

        part_w = part.get("max_power_w")
        if req_w is not None and part_w is not None:
            if float(part_w) >= float(req_w):
                passed.append(f"Power check passed: part capacity {part_w}W >= required {req_w}W")
            else:
                failed.append(f"Insufficient power: part capacity {part_w}W < required {req_w}W")
        elif req_w is not None:
            failed.append("Part max_power_w missing from catalog spec")

        is_valid = len(failed) == 0
        return is_valid, passed, failed

class PartsController:
    def __init__(self, catalogue: Dict[str, Any], ledger: BatchLedger, llm_client: ResilientLLMClient):
        self.catalogue = catalogue
        self.ledger = ledger
        self.llm_client = llm_client
        self.tools = ToolProtocol(ledger, catalogue)

    def process_batch(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for req in requests:
            req_id = req["request_id"]
            user_prompt = req["prompt"]
            
            logger.info(f"--- Processing Request {req_id} ---")
            evidence = EvidenceLog(request_id=req_id, raw_prompt=user_prompt)
            self.ledger.evidence[req_id] = evidence

            # Budget Guard
            if self.ledger.is_low_budget():
                reason = "Low budget threshold reached; referring to human safety operator."
                self.ledger.record_decision(req_id, "REFER", reason)
                results.append({"request_id": req_id, "decision": f"refer({reason})"})
                continue

            # Step 1: LLM Parameter Extraction
            extracted = self.llm_client.extract_requirements(user_prompt)
            evidence.extracted_reqs = extracted

            # Step 2: Missing requirement check / clarification
            if not extracted.get("voltage_v") or not extracted.get("connector_type"):
                clarify_resp = self.tools.clarify_request(req_id, "voltage/connector")
                if extracted.get("ambiguities"):
                    reason = f"Unclear requirements or ambiguities: {extracted['ambiguities']}"
                    self.ledger.record_decision(req_id, "REFER", reason)
                    results.append({"request_id": req_id, "decision": f"refer({reason})"})
                    continue

            # Step 3: Candidate Shortlisting using Deterministic Matcher
            shortlist = []
            for part_id, specs in self.catalogue.items():
                is_compat, passed, failed = DeterministicMatcher.is_compatible(extracted, specs)
                if is_compat:
                    shortlist.append(part_id)
                    evidence.candidate_ids.append(part_id)

            if not shortlist:
                reason = "No candidate part passed deterministic compatibility criteria."
                self.ledger.record_decision(req_id, "REFER", reason)
                results.append({"request_id": req_id, "decision": f"refer({reason})"})
                continue

            # Step 4 & 5: Tool Inspections & Stock Verification
            dispatched_part = None
            for part_id in shortlist:
                inspect_res = self.tools.inspect_part(req_id, part_id)
                if not inspect_res.get("success"):
                    continue

                stock_res = self.tools.verify_stock(req_id, part_id, extracted.get("quantity", 1))
                if stock_res.get("in_stock"):
                    dispatched_part = part_id
                    evidence.passed_checks.append(f"Stock verified for {part_id}")
                    break
                else:
                    evidence.failed_checks.append(f"Part {part_id} out of stock")

            # Step 6: Dispatch Decision
            if dispatched_part:
                reason = f"Verified compatible and in-stock: {dispatched_part}"
                self.ledger.record_decision(req_id, "DISPATCH", reason)
                results.append({"request_id": req_id, "decision": f"dispatch({dispatched_part})"})
            else:
                reason = "Compatible candidate parts were out of stock upon verification."
                self.ledger.record_decision(req_id, "REFER", reason)
                results.append({"request_id": req_id, "decision": f"refer({reason})"})

        return results