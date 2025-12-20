import random
from datetime import datetime, timedelta
from auth.db_adapter import upsert_otp, get_latest_valid_otp, mark_otp_used
from auth.utils.email_service import send_email, build_otp_email

OTP_EXPIRY_SEC = 180

def generate_otp() -> str:
    return f"{random.randint(0, 999999):06d}"

def generate_login_otp(customer_id: int, name: str, email: str):
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(seconds=OTP_EXPIRY_SEC)

    upsert_otp(customer_id, otp, "login", expiry)

    subject, html, text = build_otp_email(name, otp, "login")
    send_email(email, subject, html, text)

    return {"success": True, "expires_in": OTP_EXPIRY_SEC}

def verify_login_otp(customer_id: int, otp_code: str) -> bool:
    rec = get_latest_valid_otp(customer_id, otp_code, "login")
    if not rec:
        return False

    # 🔒 mark OTP as used to prevent replay
    mark_otp_used(rec["otp_id"])
    return True

