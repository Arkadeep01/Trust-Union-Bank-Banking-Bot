
from typing import Optional, Dict, Any
from database.core.db import run_query
import json

def get_bot_response(intent: str) -> Optional[dict]:
    """
    Fetch canned bot response JSON (stored in bot_responses.response column) for an intent.
    Returns parsed JSON or None.
    """
    q = "SELECT response FROM bot_responses WHERE intent = %s LIMIT 1;"
    rows = run_query(q, (intent,), fetch=True)
    if not rows:
        return None
    resp = rows[0].get("response") if isinstance(rows[0], dict) else rows[0][0]
    try:
        return resp if isinstance(resp, dict) else json.loads(resp)
    except Exception:
        return {"type": "text", "text": str(resp)}

def get_function_mapping(intent: str) -> Optional[dict]:
    """
    Return single function_mappings row for the intent as a dict.
    Expected fields: function_name, class_name, parameters, is_active, description
    """
    q = "SELECT function_name, class_name, parameters, is_active, description FROM function_mappings WHERE intent = %s LIMIT 1;"
    rows = run_query(q, (intent,), fetch=True)
    if not rows:
        return None
    row = rows[0]
    # ensure parameters is a dict
    params = row.get("parameters") if isinstance(row.get("parameters"), dict) else {}
    return {
        "function_name": row.get("function_name"),
        "class_name": row.get("class_name"),
        "parameters": params,
        "is_active": row.get("is_active"),
        "description": row.get("description")
    }

def log_chat(session_id: str, customer_id: int, user_query: str, bot_response: str, intent: Optional[str], verification_status: str = "general", resolved: bool = False):
    """
    Insert a chat_history record and return chat_id (or None).
    """
    q = """
    INSERT INTO chat_history (session_id, customer_id, user_query, bot_response, intent, verification_status, resolved, timestamp)
    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    RETURNING chat_id;
    """
    rows = run_query(q, (session_id, customer_id, user_query, bot_response, intent, verification_status, resolved), fetch=True)
    try:
        return rows[0].get("chat_id") if rows else None
    except Exception:
        return None
