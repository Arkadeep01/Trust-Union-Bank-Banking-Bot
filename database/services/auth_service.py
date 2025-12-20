# database/auth_service.py
import bcrypt
import logging
from database.core.db import run_query
from database.services.otp_service import generate_otp, verify_otp
from database.services.session_service import create_session, upsert_session
from typing import Optional

LOG = logging.getLogger(__name__)

def setup_mpin(customer_id: int, mpin_plain: str) -> bool:
    hashed = bcrypt.hashpw(mpin_plain.encode(), bcrypt.gensalt()).decode()
    q = """
    INSERT INTO security_mpin (customer_id, mpin_hash, created_at)
    VALUES (%s, %s, NOW())
    ON CONFLICT (customer_id) DO UPDATE SET mpin_hash = EXCLUDED.mpin_hash, created_at = NOW();
    """
    run_query(q, (customer_id, hashed), fetch=False)
    return True

def verify_mpin(customer_id: int, mpin_plain: str) -> bool:
    q = "SELECT mpin_hash FROM security_mpin WHERE customer_id = %s LIMIT 1;"
    rows = run_query(q, (customer_id,), fetch=True)
    if not rows:
        return False
    stored = rows[0].get("mpin_hash")
    if not stored:
        return False
    return bcrypt.checkpw(mpin_plain.encode(), stored.encode())

def login_via_otp(customer_id: int, purpose="login") -> Optional[str]:
    # generate otp and return it (caller sends via email/SMS)
    return generate_otp(customer_id, purpose)

def verify_login_otp(customer_id: int, code: str, purpose="login") -> bool:
    ok = verify_otp(customer_id, code, purpose)
    if ok:
        # create session row
        session = create_session(customer_id)
        return True
    return False
