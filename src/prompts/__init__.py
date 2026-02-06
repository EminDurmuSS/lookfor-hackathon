# Prompts package - Agent prompt templates
"""
System prompts for all agents.
- build_*_prompt: Dynamic prompt builders with customer context
- INTENT_CLASSIFIER_PROMPT: Intent classification template
- REFLECTION_PROMPT, REVISION_PROMPT: QA review templates
- Shared blocks: Common prompt fragments
"""

from src.prompts.account_prompt import build_account_prompt
from src.prompts.intent_classifier_prompt import INTENT_CLASSIFIER_PROMPT
from src.prompts.issue_prompt import build_issue_prompt
from src.prompts.reflection_prompt import REFLECTION_PROMPT, REVISION_PROMPT
from src.prompts.shared_blocks import (
    REASONING_FORMAT_BLOCK,
    GID_ORDER_NUMBER_BLOCK,
    CROSS_AGENT_HANDOFF_BLOCK,
)
from src.prompts.supervisor_prompt import build_supervisor_prompt
from src.prompts.wismo_prompt import build_wismo_prompt

__all__ = [
    # Prompt builders
    "build_account_prompt",
    "build_issue_prompt",
    "build_supervisor_prompt",
    "build_wismo_prompt",
    # Static prompts
    "INTENT_CLASSIFIER_PROMPT",
    "REFLECTION_PROMPT",
    "REVISION_PROMPT",
    # Shared blocks
    "REASONING_FORMAT_BLOCK",
    "GID_ORDER_NUMBER_BLOCK",
    "CROSS_AGENT_HANDOFF_BLOCK",
]
