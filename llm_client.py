import json
import os
import re
import time
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

class ResilientLLMClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: int = 15,
        max_retries: int = 3
    ):
        self.base_url = base_url or os.getenv("LLM_GATEWAY_URL", "https://api.openai.com/v1/chat/completions")
        self.api_key = api_key or os.getenv("LLM_GATEWAY_API_KEY", "")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def extract_requirements(self, user_prompt: str) -> Dict[str, Any]:
        """Extracts requirements via API if API key exists, otherwise uses dry-run fallback."""
        if not self.api_key:
            return self._mock_extract(user_prompt)

        system_instructions = (
            "You are a technical parts parsing assistant. Extract hardware requirements from everyday text.\n"
            "Return valid JSON ONLY with key fields: 'voltage_v' (float/null), 'connector_type' (string/null), "
            "'power_w' (float/null), 'current_a' (float/null), 'quantity' (int, default 1), and 'ambiguities' (list of strings)."
        )
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": f"Extract parameters for: \"{user_prompt}\""}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0
        }

        try:
            raw_response = self._post_with_retries(payload)
            return self._parse_json_response(raw_response)
        except Exception:
            # Fallback to mock extraction if API call fails
            return self._mock_extract(user_prompt)

    def _post_with_retries(self, payload: Dict[str, Any]) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        
        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(self.base_url, data=data_bytes, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    return response.read().decode("utf-8")
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                if attempt == self.max_retries:
                    raise RuntimeError(f"LLM Gateway failed after {self.max_retries} attempts: {e}")
                time.sleep(1.5 ** attempt)
        return "{}"

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        try:
            data = json.loads(response_text)
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception:
            return {
                "voltage_v": None,
                "connector_type": None,
                "power_w": None,
                "current_a": None,
                "quantity": 1,
                "ambiguities": ["Failed to parse structured JSON"]
            }

    def _mock_extract(self, user_prompt: str) -> Dict[str, Any]:
        """Simple rule-based fallback for dry-run mode without API keys."""
        text = user_prompt.lower()
        
        voltage = 12.0 if "12v" in text else (5.0 if "5v" in text else (24.0 if "24v" in text else None))
        
        connector = None
        if "5.5mm" in text or "barrel" in text:
            connector = "barrel_5.5mm"
        elif "usb-c" in text or "usb c" in text:
            connector = "usb_c"
        elif "terminal" in text:
            connector = "terminal_block"

        power = 45.0 if "45w" in text else (60.0 if "60w" in text else None)
        
        ambiguities = []
        if not voltage or not connector:
            ambiguities.append("Missing voltage or connector specifications.")

        return {
            "voltage_v": voltage,
            "connector_type": connector,
            "power_w": power,
            "current_a": None,
            "quantity": 1,
            "ambiguities": ambiguities
        }