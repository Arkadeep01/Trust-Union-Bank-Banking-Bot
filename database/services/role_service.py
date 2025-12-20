# database/role_service.py
from typing import List
from database.core.db import run_query

# Roles: customer, admin, super_admin, fraud_analyst, kyc_agent, support_agent

def get_roles() -> List[dict]:
    q = "SELECT role_id, name, description FROM roles ORDER BY name;"
    rows = run_query(q, fetch=True)
    return rows or []

def get_user_roles(admin_id: int):
    q = """
    SELECT r.name FROM roles r
    JOIN admin_roles ar ON ar.role_id = r.role_id
    WHERE ar.admin_id = %s
    """
    rows = run_query(q, (admin_id,), fetch=True)
    return [r['name'] for r in rows] if rows else []

def has_permission_admin(admin_id: int, required_role: str) -> bool:
    roles = get_user_roles(admin_id)
    return required_role in roles or "super_admin" in roles

def ensure_role_exists(role_name: str, description: str = ""):
    q = "INSERT INTO roles (name, description) VALUES (%s, %s) ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description;"
    run_query(q, (role_name, description), fetch=False)

# Initialize default roles
def bootstrap_default_roles():
    for r in ["customer", "admin", "super_admin", "fraud_analyst", "kyc_agent", "support_agent"]:
        ensure_role_exists(r, f"default {r}")
