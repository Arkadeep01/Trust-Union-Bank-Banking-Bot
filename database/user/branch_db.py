# database/user/branch_db.py

from database.core.db import run_query
import math
from typing import List, Dict, Any, Optional

# ---------------------------------------------------------
# 1. Fetch all branches
# ---------------------------------------------------------
def get_all_branches():
    q = """
        SELECT branch_code, branch_name, address, latitude, longitude,
               working_hours, contact_number
        FROM branches
    """
    return run_query(q, fetch=True) or []


# ---------------------------------------------------------
# 2. Fetch branch by location keyword (city / area)
# ---------------------------------------------------------
def get_branch_by_location(keyword: str):
    q = """
        SELECT branch_code, branch_name, address, latitude, longitude,
               working_hours, contact_number
        FROM branches
        WHERE LOWER(address) LIKE %s
           OR LOWER(branch_name) LIKE %s
    """
    like = f"%{keyword.lower()}%"
    return run_query(q, (like, like), fetch=True) or []


# ---------------------------------------------------------
# 3. Fetch branch by IFSC / branch_code
# ---------------------------------------------------------
def get_branch_by_code(branch_code: str):
    q = """
        SELECT branch_code, branch_name, address, latitude, longitude,
               working_hours, contact_number
        FROM branches
        WHERE branch_code = %s
        LIMIT 1
    """
    rows = run_query(q, (branch_code,), fetch=True)
    return rows[0] if rows else None


# ---------------------------------------------------------
# 4. Fetch all accounts of a user
# ---------------------------------------------------------
def get_user_accounts(customer_id: int):
    q = """
        SELECT account_id, account_number, ifsc_code, branch_code,
               type, balance
        FROM accounts
        WHERE customer_id = %s
    """
    return run_query(q, (customer_id,), fetch=True) or []


# ---------------------------------------------------------
# 5. Haversine formula for distance calculation
# ---------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(dlambda / 2) ** 2)

    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------
# 6. Public wrapper helpers (convenience API for services/handlers)
# ---------------------------------------------------------
def fetch_all_ifscs() -> List[Dict[str, Any]]:
    """
    Wrapper: return all branches as list of dicts (safe fallback to []).
    """
    return get_all_branches() or []


def fetch_branches_by_text(text: str) -> List[Dict[str, Any]]:
    """
    Wrapper: search branches by text (city/locality/branch name).
    """
    if not text:
        return []
    return get_branch_by_location(text) or []


def fetch_branch_by_code(branch_code: str) -> Optional[Dict[str, Any]]:
    """
    Wrapper: fetch single branch by code/IFSC.
    """
    if not branch_code:
        return None
    return get_branch_by_code(branch_code)


def fetch_accounts_for_customer(customer_id: int) -> List[Dict[str, Any]]:
    """
    Wrapper: return accounts for customer (safe empty list).
    """
    if not customer_id:
        return []
    return get_user_accounts(customer_id) or []


def fetch_branches_with_coords() -> List[Dict[str, Any]]:
    """
    Return only branches that have latitude & longitude set.
    """
    rows = get_all_branches() or []
    out: List[Dict[str, Any]] = []
    for r in rows:
        lat = r.get("latitude")
        lon = r.get("longitude")
        if lat is not None and lon is not None:
            try:
                out.append(r)
            except Exception:
                continue
    return out


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Wrapper around the existing haversine function (keeps units km).
    """
    try:
        return haversine(lat1, lon1, lat2, lon2)
    except Exception:
        # fallback local impl (same maths as the haversine above)
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2.0) ** 2 +
             math.cos(phi1) * math.cos(phi2) *
             math.sin(dlambda / 2.0) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
