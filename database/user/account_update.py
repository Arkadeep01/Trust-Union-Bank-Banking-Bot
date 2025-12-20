# database/user/account_update.py

from database.core.db import run_query
from security.audit import record_audit


def update_contact_info(customer_id: int, new_email: str = None, new_phone: str = None):
    updates = []
    params = []

    if new_email:
        updates.append("email = %s")
        params.append(new_email)

    if new_phone:
        updates.append("phone = %s")
        params.append(new_phone)

    if not updates:
        return False

    params.append(customer_id)

    q = f"UPDATE users SET {', '.join(updates)} WHERE customer_id = %s"
    run_query(q, tuple(params), fetch=False)

    record_audit("users", customer_id, "update_contact", None, {
        "email": new_email,
        "phone": new_phone
    })

    return True
