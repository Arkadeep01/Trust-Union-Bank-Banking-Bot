from typing import List, Any
from fastapi import HTTPException, status
from auth.authentication.token_manager import token_manager
from database.core.db import run_query

# -------------------------------------------------
# ROLE DEFINITIONS
# -------------------------------------------------

ROLE_CUSTOMER = "customer"
ROLE_ADMIN = "admin"
ROLE_SUPER_ADMIN = "super_admin"
ROLE_SUPPORT = "support"
ROLE_FRAUD = "fraud_analyst"

# -------------------------------------------------
# INTERNAL: SAFE JWT SUBJECT EXTRACTION
# -------------------------------------------------

def _extract_user_id(payload: dict) -> int:
    sub: Any = payload.get("sub")

    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject (sub)",
        )

    try:
        return int(sub)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )

# -------------------------------------------------
# DB ROLE FETCH
# -------------------------------------------------

def get_user_roles(user_id: int) -> List[str]:
    q = """
    SELECT r.name
    FROM roles r
    JOIN user_roles ur ON ur.role_id = r.role_id
    WHERE ur.user_id = %s
    """
    rows = run_query(q, (user_id,), fetch=True)
    return [r["name"] for r in rows] if rows else []

# -------------------------------------------------
# CORE PERMISSION CHECK
# -------------------------------------------------

def require_roles(
    token: str,
    allowed_roles: List[str],
) -> int:
    try:
        payload = token_manager.decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = _extract_user_id(payload)
    user_roles = get_user_roles(user_id)

    if not user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No roles assigned",
        )

    if not any(role in allowed_roles for role in user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return user_id

# -------------------------------------------------
# FASTAPI DEPENDENCY HELPERS
# -------------------------------------------------

def customer_only(token: str):
    return require_roles(token, [ROLE_CUSTOMER])

def admin_only(token: str):
    return require_roles(token, [ROLE_ADMIN, ROLE_SUPER_ADMIN])

def super_admin_only(token: str):
    return require_roles(token, [ROLE_SUPER_ADMIN])

def support_only(token: str):
    return require_roles(token, [ROLE_SUPPORT, ROLE_ADMIN])

def fraud_team_only(token: str):
    return require_roles(token, [ROLE_FRAUD, ROLE_ADMIN, ROLE_SUPER_ADMIN])
