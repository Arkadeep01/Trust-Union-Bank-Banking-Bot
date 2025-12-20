# database/otp_service.py
import os
import random
import string
import logging
from datetime import datetime, timedelta
import bcrypt
from database.core.db import run_query

LOG = logging.getLogger(__name__)
OTP_EXP_MIN = int(os.getenv("OTP_EXP_MIN", 5))

def _gen_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

def generate_otp(customer_id: int, purpose: str, expiry_minutes: int = OTP_EXP_MIN) -> str:
    code = _gen_code(6)
    expiry = datetime.utcnow() + timedelta(minutes=expiry_minutes)
    # store plaintext (optional) or hashed; we store hashed for security
    hashed = bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()
    q = """
    INSERT INTO otp_logs (customer_id, otp_code, expiry, purpose, attempts, used, created_at)
    VALUES (%s, %s, %s, %s, 0, FALSE, NOW());
    """
    run_query(q, (customer_id, hashed, expiry, purpose), fetch=False)
    LOG.info("OTP generated for %s, purpose=%s", customer_id, purpose)
    return code  # return plaintext so caller can send it to user

def verify_otp(customer_id: int, code: str, purpose: str) -> bool:
    q = """
    SELECT otp_id, otp_code, expiry, used FROM otp_logs
    WHERE customer_id = %s AND purpose = %s
    ORDER BY otp_id DESC LIMIT 1;
    """
    rows = run_query(q, (customer_id, purpose), fetch=True)
    if not rows:
        return False
    row = rows[0]
    if row.get("used"):
        return False
    expiry = row.get("expiry")
    if expiry and expiry < datetime.utcnow():
        return False
    stored_hash = row.get("otp_code")
    if not stored_hash:
        return False
    ok = bcrypt.checkpw(code.encode(), stored_hash.encode())
    if ok:
        # mark used
        run_query("UPDATE otp_logs SET used = TRUE WHERE otp_id = %s;", (row['otp_id'],), fetch=False)
        return True
    else:
        run_query("UPDATE otp_logs SET attempts = attempts + 1 WHERE otp_id = %s;", (row['otp_id'],), fetch=False)
        return False
