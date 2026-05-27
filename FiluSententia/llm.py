"""
Ollama client for FiluSententia.

Thin wrapper around the Ollama REST API.
Designed so a cloud backend (Gemini, Claude, etc.) can be swapped in
later by replacing this module's `generate()` signature.
"""

import json
import re

import requests

OLLAMA_BASE    = "http://localhost:11434"
DEFAULT_MODEL  = "qwen2.5:3b"
TIMEOUT_SECS   = 90   # generous — small models on CPU can be slow


def available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def generate(model: str, system: str, prompt: str) -> dict:
    """
    Call Ollama with JSON mode enforced.
    Returns parsed dict, or {"_error": "..."} on failure.
    """
    payload = {
        "model":   model,
        "system":  system,
        "prompt":  prompt,
        "format":  "json",
        "stream":  False,
        "options": {
            "temperature": 0.1,
            "num_predict": 600,
            "top_p":       0.9,
        },
    }
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json=payload,
            timeout=TIMEOUT_SECS,
        )
        r.raise_for_status()
        raw = r.json().get("response", "")
        return _parse_json(raw)
    except requests.Timeout:
        return {"_error": "timeout — model too slow, try a smaller one"}
    except requests.ConnectionError:
        return {"_error": "Ollama not reachable at localhost:11434"}
    except Exception as e:
        return {"_error": str(e)}


def _parse_json(raw: str) -> dict:
    """Best-effort JSON extraction from LLM output."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # try to find a JSON object inside prose
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {"_error": f"could not parse JSON: {raw[:120]}"}
