"""
Checkpointer setup for multi-turn conversation memory.
"""

from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()