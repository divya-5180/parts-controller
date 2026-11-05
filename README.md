# Parts Request Controller Strategy

## 1. Zero-Incompatibility Guardrail
Because a single incompatible dispatch yields a batch score of ZERO, compatibility is never left to LLM guesswork alone.
- **LLM Responsibility:** Extraction of structured attributes (`voltage_v`, `connector_type`, `power_w`).
- **Deterministic Python Engine:** Enforces voltage strictness, connector string normalization, and $P_{part} \ge P_{required}$ capacity rules.
- **Fallback Rule:** If any requirement is missing or ambiguous after 1 clarification attempt, the request is immediately **REFERRED**.

## 2. Tool Budget Optimization
Tools cost units (`inspection`: 2.0, `clarification`: 1.5, `stock_verification`: 3.0).
- **Early Filter:** Shortlists parts locally using catalogue metadata before calling API tools.
- **Lazy Evaluation:** Inspection & Stock tools are called only for candidate parts that pass deterministic matching.
- **Budget Guard:** When remaining budget falls below threshold (e.g., 15 units), high-cost optional tool paths are bypassed and uncertain requests are **REFERRED**.

## 3. Evidence Audit Trail
Every decision generates an `EvidenceLog` entry containing extracted attributes, candidate shortlists, tool costs, failed/passed checks, and an explicit action reason for compliance auditability.