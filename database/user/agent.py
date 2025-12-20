import json
from typing import List, Dict, Any, Optional
from database.core.db import run_query

def get_human_agents_by_specialization(specialization: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        if specialization:
            select_query = """
                SELECT agent_id, agent_name, department, contact_number, email, specialization
                FROM human_agents
                WHERE is_active = TRUE
                AND (%s = ANY(specialization) OR %s = ANY(specialization))
                ORDER BY agent_name
            """
            results = run_query(
                select_query,
                params=(specialization.lower(), specialization),
                fetch=True
            )
        else:
            select_query = """
                SELECT agent_id, agent_name, department, contact_number, email, specialization
                FROM human_agents
                WHERE is_active = TRUE
                ORDER BY department, agent_name
            """
            results = run_query(select_query, fetch=True)
        
        return [dict(row) for row in results] if results else []
    except Exception as e:
        print(f"❌ Error fetching human agents: {e}")
        return []
