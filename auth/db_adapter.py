from typing import Optional, Dict, Any
from database.core.connect import get_connection


# -------------------------------------------------
# Helper
# -------------------------------------------------
def _row_to_dict(cursor, row) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    if isinstance(row, dict):
        return row
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


# -------------------------------------------------
# USER LOOKUPS
# -------------------------------------------------
def find_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    if not email:
        return None
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE email = %s LIMIT 1",
            (email,)
        )
        return _row_to_dict(cur, cur.fetchone())


def find_user_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    if not phone:
        return None
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE phone = %s LIMIT 1",
            (phone,)
        )
        return _row_to_dict(cur, cur.fetchone())


def find_customer_by_account_number(account_number: str) -> Optional[Dict[str, Any]]:
    if not account_number:
        return None
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.*
            FROM accounts a
            JOIN users u ON u.customer_id = a.customer_id
            WHERE a.account_number = %s
            LIMIT 1
            """,
            (account_number,)
        )
        return _row_to_dict(cur, cur.fetchone())


# -------------------------------------------------
# OTP (matches otp_logs schema)
# -------------------------------------------------
def upsert_otp(customer_id: int, otp_hash: str, purpose: str, expiry):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO otp_logs (
                customer_id, otp_code, purpose, expiry,
                used, attempts, created_at
            )
            VALUES (%s, %s, %s, %s, FALSE, 0, NOW())
            """,
            (customer_id, otp_hash, purpose, expiry)
        )
        conn.commit()


def get_latest_valid_otp(customer_id: int, purpose: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT otp_id, otp_code, expiry
            FROM otp_logs
            WHERE customer_id = %s
              AND purpose = %s
              AND used = FALSE
              AND expiry > NOW()
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (customer_id, purpose)
        )
        return _row_to_dict(cur, cur.fetchone())


def mark_otp_used(otp_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE otp_logs SET used = TRUE WHERE otp_id = %s",
            (otp_id,)
        )
        conn.commit()


# -------------------------------------------------
# MPIN
# -------------------------------------------------
def upsert_mpin(customer_id: int, hashed_mpin: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO security_mpin (customer_id, mpin_hash, created_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (customer_id)
            DO UPDATE
            SET mpin_hash = EXCLUDED.mpin_hash,
                created_at = NOW()
            """,
            (customer_id, hashed_mpin)
        )
        conn.commit()


def get_mpin_hash(customer_id: int) -> Optional[str]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT mpin_hash
            FROM security_mpin
            WHERE customer_id = %s
            LIMIT 1
            """,
            (customer_id,)
        )
        row = cur.fetchone()
        return row[0] if row else None
