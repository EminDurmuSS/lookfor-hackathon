"""
Database module for session metadata management.
Uses 'history.db' to store session summaries for the sidebar list.
"""
import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple

DB_PATH = "history.db"

def init_db():
    """Initialize the sessions table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            customer_email TEXT,
            customer_name TEXT,
            created_at TEXT,
            preview TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_session(session_id: str, email: str, name: str, created_at: str = None):
    """Add a new session to the history."""
    if not created_at:
        created_at = datetime.utcnow().isoformat()
    
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO sessions (session_id, customer_email, customer_name, created_at, preview) VALUES (?, ?, ?, ?, ?)",
        (session_id, email, name, created_at, "New Conversation")
    )
    conn.commit()
    conn.close()

def update_preview(session_id: str, preview_text: str):
    """Update the preview text for a session (usually after first message)."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    c = conn.cursor()
    # Only update if it currently says "New Conversation" or is empty, to preserve the first topic
    # Or we can just always update it to show the latest state. 
    # Let's keep it simple: update it if we have a valid string.
    if preview_text:
        # Truncate to ~30 chars
        safe_preview = (preview_text[:27] + "...") if len(preview_text) > 30 else preview_text
        c.execute("UPDATE sessions SET preview = ? WHERE session_id = ?", (safe_preview, session_id))
    conn.commit()
    conn.close()

def list_sessions(email: Optional[str] = None) -> List[dict]:
    """List all sessions ordered by creation date (newest first). Filter by email if provided."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if email:
        c.execute("SELECT * FROM sessions WHERE customer_email = ? ORDER BY created_at DESC", (email,))
    else:
        c.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        
    rows = c.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]
