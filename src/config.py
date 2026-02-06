"""
Configuration module — environment variables, model instances, constants.
- Loads env vars (dotenv optional)
- Builds Anthropic chat models lazily/safely (dependency optional)
- Provides constants + time helper context
"""

from __future__ import annotations

import importlib
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any


# ── Optional dotenv ───────────────────────────────────────────────────────────
def _load_dotenv_if_available() -> None:
    """Load .env values when python-dotenv is installed."""
    if importlib.util.find_spec("dotenv") is None:
        return
    dotenv_module = importlib.import_module("dotenv")
    dotenv_module.load_dotenv()


_load_dotenv_if_available()


# ── Environment ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
API_URL: str = os.getenv("API_URL", "http://localhost:8080")
APP_TIMEZONE: str = os.getenv("APP_TIMEZONE", "UTC")


# ── Model Builders ───────────────────────────────────────────────────────────
def _build_chat_model(*, model: str, temperature: float, max_tokens: int) -> Any:
    """
    Create a langchain_anthropic.ChatAnthropic instance if available.
    Returns None if langchain_anthropic isn't installed.
    """
    if importlib.util.find_spec("langchain_anthropic") is None:
        return None

    anthropic_module = importlib.import_module("langchain_anthropic")
    ChatAnthropic = getattr(anthropic_module, "ChatAnthropic")

    # If the key is missing, still construct the object (some env managers inject later),
    # but you can choose to raise instead by uncommenting below.
    # if not ANTHROPIC_API_KEY:
    #     raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    return ChatAnthropic(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=ANTHROPIC_API_KEY,
    )


# ── Model Instances ──────────────────────────────────────────────────────────
sonnet_llm = _build_chat_model(
    model="claude-sonnet-4-20250514",
    temperature=0.0,
    max_tokens=2048,
)

haiku_llm = _build_chat_model(
    model="claude-haiku-4-5-20251001",
    temperature=0.0,
    max_tokens=1024,
)


# ── Constants ────────────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD: int = 80
INTENT_SHIFT_THRESHOLD: int = 85
MAX_HANDOFFS_PER_TURN: int = 1
MAX_REFLECTION_CYCLES: int = 1

VALID_INTENTS: set[str] = {
    "WISMO",
    "WRONG_MISSING",
    "NO_EFFECT",
    "REFUND",
    "ORDER_MODIFY",
    "SUBSCRIPTION",
    "DISCOUNT",
    "POSITIVE",
    "GENERAL",
}

INTENT_TO_AGENT: dict[str, str] = {
    "WISMO": "wismo_agent",
    "WRONG_MISSING": "issue_agent",
    "NO_EFFECT": "issue_agent",
    "REFUND": "issue_agent",
    "ORDER_MODIFY": "account_agent",
    "SUBSCRIPTION": "account_agent",
    "DISCOUNT": "account_agent",
    "POSITIVE": "account_agent",
    "GENERAL": "supervisor",
}


# ── Time Helpers ─────────────────────────────────────────────────────────────
def get_current_context() -> dict[str, str]:
    """Return current date, day-of-week and wait-promise string."""
    tz = ZoneInfo(APP_TIMEZONE)
    now = datetime.now(tz)
    day = now.weekday()  # 0=Mon … 6=Sun

    if day <= 2:  # Mon / Tue / Wed
        wait_promise = "this Friday"
    else:  # Thu / Fri / Sat / Sun
        wait_promise = "early next week"

    return {
        "current_date": now.strftime("%Y-%m-%d"),
        "day_of_week": now.strftime("%A"),
        "wait_promise": wait_promise,
    }
