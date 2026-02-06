"""
Checkpointer setup for multi-turn conversation memory.
Uses SqliteSaver to persist graph state to 'history.db'.
"""

import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

# Connect to the SAME database file used for session metadata
# check_same_thread=False is needed for FastAPI multithreading
conn = sqlite3.connect("history.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)