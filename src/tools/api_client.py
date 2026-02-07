"""
Generic API client with retry logic for the hackathon tool endpoints.
Supports both async (preferred) and sync (fallback) modes.
"""

from __future__ import annotations

import httpx

from src.config import API_URL


# Module-level async client (connection pooling)
_async_client: httpx.AsyncClient | None = None


def _get_async_client() -> httpx.AsyncClient:
    """Get or create async HTTP client."""
    global _async_client
    if _async_client is None or _async_client.is_closed:
        _async_client = httpx.AsyncClient(timeout=15.0)
    return _async_client


async def api_call_async(endpoint: str, payload: dict) -> dict:
    """
    Async POST to ``{API_URL}/hackathon/{endpoint}`` with one automatic retry.
    Preferred method for use in async agent nodes.
    """
    url = f"{API_URL}/hackathon/{endpoint}"
    headers = {"Content-Type": "application/json"}
    client = _get_async_client()

    for attempt in range(2):
        try:
            resp = await client.post(url, json=payload, headers=headers)
            result = resp.json()
            if not isinstance(result, dict):
                return {"success": False, "error": "Unexpected response format"}
            return result
        except httpx.TimeoutException:
            if attempt == 0:
                continue
            return {"success": False, "error": "API timeout after retry"}
        except Exception as exc:
            return {"success": False, "error": f"API call failed: {exc}"}

    return {"success": False, "error": "API call failed unexpectedly"}


def api_call(endpoint: str, payload: dict) -> dict:
    """
    Sync POST to ``{API_URL}/hackathon/{endpoint}`` with one automatic retry.
    Fallback for sync contexts. For async, use api_call_async instead.
    """
    url = f"{API_URL}/hackathon/{endpoint}"
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