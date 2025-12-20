import bcrypt
from auth.db_adapter import upsert_mpin, get_mpin_hash

def set_mpin(customer_id: int, mpin: str):
    if not mpin.isdigit() or len(mpin) < 4:
        raise ValueError("Invalid MPIN")

    hashed = bcrypt.hashpw(mpin.encode(), bcrypt.gensalt()).decode()
    upsert_mpin(customer_id, hashed)

def verify_mpin(customer_id: int, mpin: str) -> bool:
    stored = get_mpin_hash(customer_id)
    if not stored:
        return False
    return bcrypt.checkpw(mpin.encode(), stored.encode())

