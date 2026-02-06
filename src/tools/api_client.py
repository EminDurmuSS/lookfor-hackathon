"""
Generic API client with retry logic for the hackathon tool endpoints.
"""

from __future__ import annotations

import httpx

from src.config import API_URL


def api_call(endpoint: str, payload: dict) -> dict:
    """
    POST to ``{API_URL}/hackhaton/{endpoint}`` with one automatic retry on
    timeout.  Always returns a dict with at least ``success`` key.
    """
    url = f"{API_URL}/hackhaton/{endpoint}"
    headers = {"Content-Type": "application/json"}

    for attempt in range(2):
        timeout = 10.0 if attempt == 0 else 15.0
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
            result = resp.json()
            if not isinstance(result, dict):
                return {"success": False, "error": "Unexpected response format"}
            return result
        except httpx.TimeoutException:
            if attempt == 0:
                continue  # retry once
            return {"success": False, "error": "API timeout after retry — please try again"}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"API call failed: {exc}"}

    # Should never reach here, but just in case
    return {"success": False, "error": "API call failed unexpectedly"}