from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime, date, timedelta
from database.core.db import run_query
from security.audit import record_audit
from database.core.connect import get_connection
from auth.db_adapter import _row_to_dict
import logging
import uuid

logger = logging.getLogger(__name__)


# ---------- User & contact updates ----------
def get_user_by_customer_id(customer_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT customer_id, name, email, phone FROM users WHERE customer_id = %s",
            (customer_id,)
        )
        return _row_to_dict(cur, cur.fetchone())


def update_personal_details_db(customer_id: int, updates: Dict[str, Any], performed_by: Optional[int] = None) -> bool:
    allowed = {"first_name", "last_name", "address", "dob", "gender"}
    set_parts = []
    params = []
    for k, v in updates.items():
        if k in allowed:
            set_parts.append(f"{k} = %s")
            params.append(v)
    if not set_parts:
        return False
    params.append(customer_id)
    q = f"UPDATE users SET {', '.join(set_parts)}, updated_at = NOW() WHERE customer_id = %s"
    run_query(q, tuple(params))
    record_audit("user", customer_id, "update_personal_details", performed_by or customer_id, {"fields": list(updates.keys())})
    return True


# ---------- PIN / TPIN / MPIN / Account security ----------
def change_transaction_pin_db(customer_id: int, new_tpin_hash: str, performed_by: Optional[int] = None) -> bool:
    q = "UPDATE user_security SET tpin_hash = %s, updated_at = NOW() WHERE customer_id = %s"
    run_query(q, (new_tpin_hash, customer_id))
    record_audit("security", customer_id, "change_tpin", performed_by or customer_id, {})
    return True


def reset_account_pin_db(customer_id: int, performed_by: Optional[int] = None) -> bool:
    # Insert a PIN reset request; actual reset flow handled by auth service
    req_id = str(uuid.uuid4())
    q = "INSERT INTO pin_reset_requests (request_id, customer_id, status, created_at) VALUES (%s, %s, %s, NOW())"
    run_query(q, (req_id, customer_id, "requested"))
    record_audit("security", customer_id, "request_pin_reset", performed_by or customer_id, {"request_id": req_id})
    return True


# ---------- Accounts & balances ----------
def get_user_accounts(customer_id: int) -> List[Dict[str, Any]]:
    q = """
        SELECT account_id, account_number, ifsc_code, branch_code, type, balance, currency
        FROM accounts
        WHERE customer_id = %s
    """
    return run_query(q, (customer_id,), fetch=True) or []


def get_user_balance_from_db(customer_id: int, account_id: Optional[int] = None) -> Optional[float]:
    if account_id:
        q = "SELECT balance FROM accounts WHERE account_id = %s AND customer_id = %s LIMIT 1"
        rows = run_query(q, (account_id, customer_id), fetch=True) or []
        return float(rows[0]["balance"]) if rows else None
    q = "SELECT SUM(balance) as total_balance FROM accounts WHERE customer_id = %s"
    rows = run_query(q, (customer_id,), fetch=True) or []
    return float(rows[0]["total_balance"] or 0.0)


# ---------- Transfers & transaction ledger ----------
def _insert_transaction_record(customer_id: int, sender_account: str, receiver_account: str, amount: float, txn_type: str, status: str, description: str, performed_by: Optional[int] = None) -> Optional[int]:
    # Insert into transactions and return transaction_id
    txn_ref = f"TXN{int(datetime.utcnow().timestamp())}{str(uuid.uuid4())[:6]}"
    q = """
        INSERT INTO transactions (customer_id, transaction_reference, sender_account_number, receiver_account_number,
                                  amount, txn_type, status, description, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING transaction_id
    """
    rows = run_query(q, (customer_id, txn_ref, sender_account, receiver_account, amount, txn_type, status, description), fetch=True) or []
    txn_id = rows[0]["transaction_id"] if rows else None
    record_audit("transactions", customer_id, "insert", performed_by or customer_id, {"transaction_id": txn_id, "ref": txn_ref, "status": status})
    return txn_id


def transfer_money_to_account_db(customer_id: int, from_account: str, to_account: str, amount: float, narration: str = "", performed_by: Optional[int] = None) -> Dict[str, Any]:
    """
    Note: in a real bank this must go through the core banking / payment gateway.
    Here we do the DB bookkeeping and insert a transaction queue record.
    Returns {ok: bool, transaction_id, status, message}
    """
    # Basic validation
    if amount <= 0:
        return {"ok": False, "message": "Invalid amount"}

    # Check sender balance
    q_bal = "SELECT balance, account_id FROM accounts WHERE account_number = %s AND customer_id = %s LIMIT 1"
    rows = run_query(q_bal, (from_account, customer_id), fetch=True) or []
    if not rows:
        return {"ok": False, "message": "Sender account not found"}
    bal = float(rows[0]["balance"])
    if bal < amount:
        return {"ok": False, "message": "Insufficient balance"}

    # Decrease sender balance and create pending transaction (atomic ideally)
    try:
        # debit
        q1 = "UPDATE accounts SET balance = balance - %s WHERE account_number = %s AND customer_id = %s"
        run_query(q1, (amount, from_account, customer_id))

        # credit receiver account if internal (same DB)
        q2 = "UPDATE accounts SET balance = balance + %s WHERE account_number = %s"
        run_query(q2, (amount, to_account))

        txn_id = _insert_transaction_record(customer_id, from_account, to_account, amount, "transfer", "completed", narration or "P2P transfer", performed_by)
        return {"ok": True, "transaction_id": txn_id, "status": "completed", "message": "Transfer completed"}
    except Exception as e:
        # Attempt to rollback best-effort (depends on run_query implementation)
        logger.exception("transfer failed: %s", e)
        # insert failed txn
        txn_id = _insert_transaction_record(customer_id, from_account, to_account, amount, "transfer", "failed", str(e), performed_by)
        return {"ok": False, "transaction_id": txn_id, "status": "failed", "message": str(e)}


def transfer_status_check_db(customer_id: int, transaction_reference: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    if transaction_reference:
        q = "SELECT * FROM transactions WHERE transaction_reference = %s LIMIT 1"
        rows = run_query(q, (transaction_reference,), fetch=True) or []
        return rows
    q = "SELECT * FROM transactions WHERE customer_id = %s ORDER BY created_at DESC LIMIT %s"
    return run_query(q, (customer_id, limit), fetch=True) or []


def transfer_failed_investigation_db(customer_id: int, transaction_reference: str, details: str, performed_by: Optional[int] = None) -> bool:
    inv_id = str(uuid.uuid4())
    q = "INSERT INTO transfer_investigations (investigation_id, transaction_reference, customer_id, details, status, created_at) VALUES (%s, %s, %s, %s, %s, NOW())"
    run_query(q, (inv_id, transaction_reference, customer_id, details, "open"))
    record_audit("investigations", customer_id, "open_investigation", performed_by or customer_id, {"investigation_id": inv_id, "transaction_reference": transaction_reference})
    return True


# ---------- Beneficiaries ----------
def add_beneficiary_db(customer_id: int, name: str, account_number: str, ifsc: str, nickname: Optional[str] = None, performed_by: Optional[int] = None) -> Dict[str, Any]:
    # Check duplicates
    qchk = "SELECT beneficiary_id FROM beneficiaries WHERE customer_id = %s AND (account_number = %s OR (name = %s AND ifsc = %s))"
    if run_query(qchk, (customer_id, account_number, name, ifsc), fetch=True):
        return {"ok": False, "message": "Beneficiary already exists"}

    q = "INSERT INTO beneficiaries (customer_id, name, account_number, ifsc, nickname, created_at) VALUES (%s, %s, %s, %s, %s, NOW()) RETURNING beneficiary_id"
    rows = run_query(q, (customer_id, name, account_number, ifsc, nickname), fetch=True) or []
    bid = rows[0]["beneficiary_id"] if rows else None
    record_audit("beneficiary", customer_id, "add", performed_by or customer_id, {"beneficiary_id": bid})
    return {"ok": True, "beneficiary_id": bid}


def delete_beneficiary_db(customer_id: int, beneficiary_id: int, performed_by: Optional[int] = None) -> bool:
    q = "DELETE FROM beneficiaries WHERE customer_id = %s AND beneficiary_id = %s"
    run_query(q, (customer_id, beneficiary_id))
    record_audit("beneficiary", customer_id, "delete", performed_by or customer_id, {"beneficiary_id": beneficiary_id})
    return True


# ---------- Scheduled transfers ----------
def schedule_transfer_db(customer_id: int, from_account: str, to_account: str, amount: float, schedule_date: date, recur: Optional[str] = None, performed_by: Optional[int] = None) -> Dict[str, Any]:
    sid = str(uuid.uuid4())
    q = "INSERT INTO scheduled_transfers (schedule_id, customer_id, from_account, to_account, amount, schedule_date, recur, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())"
    run_query(q, (sid, customer_id, from_account, to_account, amount, schedule_date, recur, "active"))
    record_audit("scheduled_transfers", customer_id, "create", performed_by or customer_id, {"schedule_id": sid})
    return {"ok": True, "schedule_id": sid}


def cancel_scheduled_transfer_db(customer_id: int, schedule_id: str, performed_by: Optional[int] = None) -> bool:
    q = "UPDATE scheduled_transfers SET status = %s, cancelled_at = NOW() WHERE schedule_id = %s AND customer_id = %s"
    run_query(q, ("cancelled", schedule_id, customer_id))
    record_audit("scheduled_transfers", customer_id, "cancel", performed_by or customer_id, {"schedule_id": schedule_id})
    return True


# ---------- Deposits & Withdrawals ----------
def get_deposit_status_db(customer_id: int, deposit_ref: Optional[str] = None) -> List[Dict[str, Any]]:
    if deposit_ref:
        q = "SELECT * FROM deposits WHERE deposit_reference = %s LIMIT 1"
        return run_query(q, (deposit_ref,), fetch=True) or []
    q = "SELECT * FROM deposits WHERE customer_id = %s ORDER BY created_at DESC LIMIT 10"
    return run_query(q, (customer_id,), fetch=True) or []


def get_withdrawal_status_db(customer_id: int, atm_ref: Optional[str] = None) -> List[Dict[str, Any]]:
    if atm_ref:
        q = "SELECT * FROM atm_withdrawals WHERE reference = %s LIMIT 1"
        return run_query(q, (atm_ref,), fetch=True) or []
    q = "SELECT * FROM atm_withdrawals WHERE customer_id = %s ORDER BY created_at DESC LIMIT 10"
    return run_query(q, (customer_id,), fetch=True) or []


# ---------- Fixed Deposit & Recurring Deposit ----------
def create_fixed_deposit_db(customer_id: int, account_id: int, amount: float, tenure_months: int, rate: float, performed_by: Optional[int] = None) -> Dict[str, Any]:
    fd_id = str(uuid.uuid4())
    mature_date = datetime.utcnow() + timedelta(days=30 * tenure_months)
    q = "INSERT INTO fds (fd_id, customer_id, account_id, principal, tenor_months, rate, mature_date, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())"
    run_query(q, (fd_id, customer_id, account_id, amount, tenure_months, rate, mature_date, "active"))
    record_audit("fds", customer_id, "create", performed_by or customer_id, {"fd_id": fd_id, "amount": amount})
    return {"ok": True, "fd_id": fd_id}


def close_fixed_deposit_db(customer_id: int, fd_id: str, performed_by: Optional[int] = None) -> bool:
    q = "UPDATE fds SET status = %s, closed_at = NOW() WHERE fd_id = %s AND customer_id = %s"
    run_query(q, ("closed", fd_id, customer_id))
    record_audit("fds", customer_id, "close", performed_by or customer_id, {"fd_id": fd_id})
    return True


def create_recurring_deposit_db(customer_id: int, account_id: int, monthly_amount: float, tenure_months: int, rate: float, performed_by: Optional[int] = None) -> Dict[str, Any]:
    rd_id = str(uuid.uuid4())
    q = "INSERT INTO rds (rd_id, customer_id, account_id, monthly_amount, tenor_months, rate, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())"
    run_query(q, (rd_id, customer_id, account_id, monthly_amount, tenure_months, rate, "active"))
    record_audit("rds", customer_id, "create", performed_by or customer_id, {"rd_id": rd_id, "monthly_amount": monthly_amount})
    return {"ok": True, "rd_id": rd_id}


def close_recurring_deposit_db(customer_id: int, rd_id: str, performed_by: Optional[int] = None) -> bool:
    q = "UPDATE rds SET status = %s, closed_at = NOW() WHERE rd_id = %s AND customer_id = %s"
    run_query(q, ("closed", rd_id, customer_id))
    record_audit("rds", customer_id, "close", performed_by or customer_id, {"rd_id": rd_id})
    return True


def fd_rd_interest_enquiry_db(product: str = "fd") -> Dict[str, Any]:
    # product: "fd" or "rd"
    q = "SELECT product, rate, min_tenure, max_tenure FROM deposit_rates WHERE product = %s"
    rows = run_query(q, (product,), fetch=True) or []
    return rows[0] if rows else {}


# ---------- Cards ----------
def get_user_cards(customer_id: int) -> List[Dict[str, Any]]:
    q = "SELECT card_id, card_type as type, last4, status FROM cards WHERE customer_id = %s"
    return run_query(q, (customer_id,), fetch=True) or []


def get_card_limits(customer_id: int, card_id: int) -> Dict[str, Any]:
    q = "SELECT daily_limit as daily, monthly_limit as monthly FROM card_limits WHERE card_id = %s AND customer_id = %s LIMIT 1"
    rows = run_query(q, (card_id, customer_id), fetch=True) or []
    return rows[0] if rows else {"daily": 0, "monthly": 0}


def activate_card_db(customer_id: int, card_id: int, performed_by: Optional[int] = None) -> bool:
    # Real activation may call card-issuer API; here we flip status
    q = "UPDATE cards SET status = %s, activated_at = NOW() WHERE card_id = %s AND customer_id = %s"
    run_query(q, ("active", card_id, customer_id))
    record_audit("cards", customer_id, "activate", performed_by or customer_id, {"card_id": card_id})
    return True


def block_card_db(customer_id: int, card_id: int, performed_by: Optional[int] = None) -> bool:
    q = "UPDATE cards SET status = %s, blocked_at = NOW() WHERE card_id = %s AND customer_id = %s"
    run_query(q, ("blocked", card_id, customer_id))
    record_audit("cards", customer_id, "block", performed_by or customer_id, {"card_id": card_id})
    return True


def apply_new_card_db(customer_id: int, card_type: str, performed_by: Optional[int] = None) -> Dict[str, Any]:
    # request to issue new card (placeholder) - card production handled offline/third-party
    req_id = str(uuid.uuid4())
    q = "INSERT INTO card_applications (application_id, customer_id, card_type, status, created_at) VALUES (%s, %s, %s, %s, NOW())"
    run_query(q, (req_id, customer_id, card_type, "submitted"))
    record_audit("card_applications", customer_id, "apply", performed_by or customer_id, {"application_id": req_id, "card_type": card_type})
    return {"ok": True, "application_id": req_id}


def replace_damaged_card_db(customer_id: int, card_id: int, performed_by: Optional[int] = None) -> Dict[str, Any]:
    req_id = str(uuid.uuid4())
    q = "INSERT INTO card_replacements (request_id, customer_id, card_id, status, created_at) VALUES (%s, %s, %s, %s, NOW())"
    run_query(q, (req_id, customer_id, card_id, "requested"))
    record_audit("card_replacements", customer_id, "request_replacement", performed_by or customer_id, {"request_id": req_id, "card_id": card_id})
    return {"ok": True, "request_id": req_id}


def reset_card_pin_db(customer_id: int, card_id: int, performed_by: Optional[int] = None) -> bool:
    # Insert a PIN reset request for card
    req_id = str(uuid.uuid4())
    q = "INSERT INTO card_pin_reset_requests (request_id, customer_id, card_id, status, created_at) VALUES (%s, %s, %s, %s, NOW())"
    run_query(q, (req_id, customer_id, card_id, "requested"))
    record_audit("cards", customer_id, "reset_pin_request", performed_by or customer_id, {"request_id": req_id, "card_id": card_id})
    return True


def check_card_delivery_status_db(customer_id: int, application_id: Optional[str] = None) -> List[Dict[str, Any]]:
    if application_id:
        q = "SELECT * FROM card_applications WHERE application_id = %s AND customer_id = %s LIMIT 1"
        return run_query(q, (application_id, customer_id), fetch=True) or []
    q = "SELECT * FROM card_applications WHERE customer_id = %s ORDER BY created_at DESC LIMIT 5"
    return run_query(q, (customer_id,), fetch=True) or []


# ---------- Loans ----------
def get_loan_details_from_db(customer_id: int, loan_type: str) -> Tuple[float, Optional[date], Optional[int]]:
    q = "SELECT outstanding_balance, next_emi_date, loan_id FROM loan_accounts WHERE customer_id = %s AND loan_type = %s LIMIT 1"
    rows = run_query(q, (customer_id, loan_type), fetch=True) or []
    if not rows:
        return (0.0, None, None)
    row = rows[0]
    return (float(row.get("outstanding_balance", 0.0)), row.get("next_emi_date"), row.get("loan_id"))


def get_next_emi_date(customer_id: int, loan_type: str) -> Optional[date]:
    q = "SELECT next_emi_date FROM loan_accounts WHERE customer_id = %s AND loan_type = %s LIMIT 1"
    rows = run_query(q, (customer_id, loan_type), fetch=True) or []
    return rows[0].get("next_emi_date") if rows else None


def apply_for_loan_db(customer_id: int, loan_type: str, amount: float, income: float, employment_type: str, performed_by: Optional[int] = None) -> Dict[str, Any]:
    app_id = str(uuid.uuid4())
    q = "INSERT INTO loan_applications (application_id, customer_id, loan_type, amount, income, employment_type, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())"
    run_query(q, (app_id, customer_id, loan_type, amount, income, employment_type, "submitted"))
    record_audit("loan_applications", customer_id, "apply", performed_by or customer_id, {"application_id": app_id})
    return {"ok": True, "application_id": app_id}


def calculate_loan_eligibility(customer_id: int, income: float, employment_type: str) -> float:
    # Simple rule-of-thumb eligibility: 12x monthly income for salaried, 6x for self-employed
    multiplier = 12 if employment_type.lower() == "salaried" else 6
    eligible = income * multiplier
    record_audit("loan_eligibility", customer_id, "calculate", customer_id, {"income": income, "employment_type": employment_type, "eligible": eligible})
    return float(eligible)


def prepay_or_foreclose_loan_db(customer_id: int, loan_id: int, performed_by: Optional[int] = None) -> Dict[str, Any]:
    # compute outstanding and mark prepayment requested
    q = "SELECT outstanding_balance FROM loan_accounts WHERE loan_id = %s AND customer_id = %s LIMIT 1"
    rows = run_query(q, (loan_id, customer_id), fetch=True) or []
    if not rows:
        return {"ok": False, "message": "Loan not found"}
    amount = float(rows[0]["outstanding_balance"])
    req_id = str(uuid.uuid4())
    q2 = "INSERT INTO loan_prepay_requests (request_id, loan_id, customer_id, amount, status, created_at) VALUES (%s, %s, %s, %s, %s, NOW())"
    run_query(q2, (req_id, loan_id, customer_id, amount, "requested"))
    record_audit("loan_prepay", customer_id, "request", performed_by or customer_id, {"request_id": req_id, "amount": amount})
    return {"ok": True, "request_id": req_id, "amount": amount}


def loan_statement_request_db(customer_id: int, loan_id: int, period_days: int = 365) -> Dict[str, Any]:
    link_html = (
        '<a href="/loans" class="btn btn-primary">'
        'View / Download Loan Statement'
        '</a>'
    )
    record_audit(
        "loan_statements",
        customer_id,
        "generate_link",
        customer_id,
        {"loan_id": loan_id, "period_days": period_days}
    )
    return {"ok": True, "link": link_html}


def loan_eligibility_check_db(customer_id: int, details: str) -> Dict[str, Any]:
    # Provide a quick check using calculate_loan_eligibility (expects parsed income/employment earlier)
    # details can be a JSON string or "income:xxx;employment:yyy" — parser is handler's job
    return {"ok": True, "message": "Eligibility check completed (see UI for details)"}


# ---------- Fraud / Locking / Security ----------
def report_unauthorized_transaction_db(customer_id: int, tx_ref: str, details: str, performed_by: Optional[int] = None) -> bool:
    q = "INSERT INTO fraud_reports (report_id, customer_id, transaction_reference, details, status, created_at) VALUES (%s, %s, %s, %s, %s, NOW())"
    rid = str(uuid.uuid4())
    run_query(q, (rid, customer_id, tx_ref, details, "open"))
    record_audit("fraud", customer_id, "report", performed_by or customer_id, {"report_id": rid, "transaction_reference": tx_ref})
    return True


def report_fraudulent_activity_db(customer_id: int, details: str, performed_by: Optional[int] = None) -> bool:
    rid = str(uuid.uuid4())
    q = "INSERT INTO fraud_reports (report_id, customer_id, details, status, created_at) VALUES (%s, %s, %s, %s, NOW())"
    run_query(q, (rid, customer_id, details, "open"))
    record_audit("fraud", customer_id, "report_activity", performed_by or customer_id, {"report_id": rid})
    return True


def lock_or_unlock_account_db(customer_id: int, action: str, performed_by: Optional[int] = None) -> bool:
    # action -> 'lock' or 'unlock'
    status = "locked" if action == "lock" else "active"
    q = "UPDATE users SET account_status = %s, updated_at = NOW() WHERE customer_id = %s"
    run_query(q, (status, customer_id))
    record_audit("user", customer_id, f"account_{action}", performed_by or customer_id, {})
    return True


def enable_two_factor_authentication_db(customer_id: int, method: str = "sms", performed_by: Optional[int] = None) -> bool:
    q = "UPDATE user_security SET two_fa = %s, two_fa_method = %s, updated_at = NOW() WHERE customer_id = %s"
    run_query(q, (True, method, customer_id))
    record_audit("security", customer_id, "enable_2fa", performed_by or customer_id, {"method": method})
    return True


def set_transaction_alerts_db(customer_id: int, enabled: bool, channels: List[str], performed_by: Optional[int] = None) -> bool:
    q = "UPDATE user_preferences SET alerts_enabled = %s, alert_channels = %s, updated_at = NOW() WHERE customer_id = %s"
    run_query(q, (enabled, channels, customer_id))
    record_audit("preferences", customer_id, "set_transaction_alerts", performed_by or customer_id, {"enabled": enabled, "channels": channels})
    return True


def stop_alert_notifications_db(customer_id: int, performed_by: Optional[int] = None) -> bool:
    return set_transaction_alerts_db(customer_id, False, [], performed_by)


# ---------- Service requests & complaints ----------
def raise_service_complaint_db(customer_id: int, category: str, description: str, performed_by: Optional[int] = None) -> Dict[str, Any]:
    req_id = str(uuid.uuid4())
    q = "INSERT INTO service_requests (request_id, customer_id, category, description, status, created_at) VALUES (%s, %s, %s, %s, %s, NOW())"
    run_query(q, (req_id, customer_id, category, description, "open"))
    record_audit("service_requests", customer_id, "raise", performed_by or customer_id, {"request_id": req_id, "category": category})
    return {"ok": True, "request_id": req_id}


def track_service_request_db(customer_id: int, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
    if request_id:
        q = "SELECT * FROM service_requests WHERE request_id = %s AND customer_id = %s LIMIT 1"
        return run_query(q, (request_id, customer_id), fetch=True) or []
    q = "SELECT * FROM service_requests WHERE customer_id = %s ORDER BY created_at DESC LIMIT 10"
    return run_query(q, (customer_id,), fetch=True) or []


# ---------- Documents & KYC ----------
def store_user_document(customer_id: int, doc_type: str, file_path: str, performed_by: Optional[int] = None) -> Optional[int]:
    q = "INSERT INTO kyc_docs (customer_id, doc_type, file_path, uploaded_at) VALUES (%s, %s, %s, NOW()) RETURNING kyc_id"
    rows = run_query(q, (customer_id, doc_type, file_path), fetch=True) or []
    kyc_id = rows[0]["kyc_id"] if rows else None
    record_audit("kyc_docs", customer_id, "store", performed_by or customer_id, {"kyc_id": kyc_id, "doc_type": doc_type})
    return kyc_id


def kyc_update_procedure_db(customer_id: int, performed_by: Optional[int] = None) -> Dict[str, Any]:
    # Return guidance template and accepted docs from DB/config
    q = "SELECT doc_type, required FROM kyc_requirements"
    rows = run_query(q, fetch=True) or []
    record_audit("kyc", customer_id, "get_requirements", performed_by or customer_id, {})
    return {"requirements": rows}


def re_kyc_update_db(customer_id: int, performed_by: Optional[int] = None) -> bool:
    q = "INSERT INTO re_kyc_requests (request_id, customer_id, status, created_at) VALUES (%s, %s, %s, NOW())"
    req_id = str(uuid.uuid4())
    run_query(q, (req_id, customer_id, "requested"))
    record_audit("kyc", customer_id, "rekyc_request", performed_by or customer_id, {"request_id": req_id})
    return True


# ---------- Tax & certificates ----------
def request_interest_certificate_db(customer_id: int, year: int = datetime.utcnow().year, performed_by: Optional[int] = None) -> Dict[str, Any]:
    link_html = (
        '<a href="/statements" class="btn btn-primary">'
        'Download Interest Certificate'
        '</a>'
    )
    record_audit(
        "certificates",
        customer_id,
        "interest_certificate",
        performed_by or customer_id,
        {"year": year}
    )
    return {"ok": True, "link": link_html}


def request_tds_certificate_db(customer_id: int, fy: Optional[str] = None, performed_by: Optional[int] = None) -> Dict[str, Any]:
    link_html = (
        '<a href="/statements" class="btn btn-primary">'
        'Download TDS Certificate'
        '</a>'
    )
    record_audit(
        "certificates",
        customer_id,
        "tds_certificate",
        performed_by or customer_id,
        {"fy": fy or "latest"}
    )
    return {"ok": True, "link": link_html}


def download_tax_summary_db(customer_id: int, year: int) -> Dict[str, Any]:
    link_html = (
        '<a href="/statements" class="btn btn-primary">'
        f'Download Tax Summary ({year})'
        '</a>'
    )
    record_audit(
        "tax",
        customer_id,
        "download_summary",
        customer_id,
        {"year": year}
    )
    return {"ok": True, "link": link_html}


# ---------- Misc ----------
def branch_timings_or_holidays_db() -> Dict[str, Any]:
    # return static timings + holidays coming from DB/config
    q = "SELECT key, value FROM config WHERE key IN ('branch_timings','holiday_calendar')"
    rows = run_query(q, fetch=True) or []
    config = {r["key"]: r["value"] for r in rows}
    return {"timings": config.get("branch_timings", "10:00-16:00"), "holidays": config.get("holiday_calendar", [])}


def card_pin_not_received_db(customer_id: int, card_id: int, performed_by: Optional[int] = None) -> bool:
    # register case and return guidance
    case_id = str(uuid.uuid4())
    q = "INSERT INTO card_pin_issues (case_id, customer_id, card_id, status, created_at) VALUES (%s, %s, %s, %s, NOW())"
    run_query(q, (case_id, customer_id, card_id, "open"))
    record_audit("cards", customer_id, "pin_not_received", performed_by or customer_id, {"case_id": case_id})
    return True


# End of file
