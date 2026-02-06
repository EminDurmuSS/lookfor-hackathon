"""
Configuration module — environment variables, model instances, constants.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

# ── Environment ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
API_URL: str = os.getenv("API_URL", "http://localhost:8080")
APP_TIMEZONE: str = os.getenv("APP_TIMEZONE", "UTC")

# ── Model Instances ──────────────────────────────────────────────────────────
sonnet_llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    temperature=0,
    max_tokens=2048,
    api_key=ANTHROPIC_API_KEY,
)

haiku_llm = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    temperature=0,
    max_tokens=1024,
    api_key=ANTHROPIC_API_KEY,
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