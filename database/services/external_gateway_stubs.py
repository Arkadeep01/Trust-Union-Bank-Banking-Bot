# database/services/external_gateway_stubs.py
from typing import Optional, Dict, Any
import logging
import uuid
from security.audit import record_audit

logger = logging.getLogger(__name__)

COMING_SOON_MSG = (
    "The banking system is working on these features, you will shortly be able to "
    "use these features also. For more info contact our helpline: 1900 799 0010"
)

STANDARD_RESPONSE: Dict[str, Any] = {
    "ok": False,
    "code": "EXTERNAL_STUB",
    "message": COMING_SOON_MSG
}


def _make_response(action: str, customer_id: Optional[int], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    performed_by = customer_id if customer_id is not None else 0
    meta: Dict[str, Any] = {"action": action}
    if extra:
        for k, v in extra.items():
            meta[k] = v

    meta["stub_request_id"] = str(uuid.uuid4())
    try:
        record_audit("external_stub", customer_id or 0, action, performed_by, meta)
    except Exception as e:
        logger.exception("audit failed for external stub action=%s: %s", action, e)

    logger.info("external stub called action=%s customer_id=%s meta=%s", action, customer_id, meta)
    resp = dict(STANDARD_RESPONSE)
    resp["meta"] = dict(meta)
    return resp


def funds_transfer_via_core_banking(
    customer_id: Optional[int],
    from_account: str,
    to_account: str,
    amount: float,
    currency: str = "INR",
    narration: Optional[str] = None,
    request_meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    extra: Dict[str, Any] = {
        "from_account_masked": (from_account[-6:] if from_account and len(from_account) > 6 else from_account),
        "to_account_masked": (to_account[-6:] if to_account and len(to_account) > 6 else to_account),
        "amount": float(amount),
        "currency": currency,
        "narration_present": bool(narration)
    }
    if request_meta:
        extra["client_meta"] = request_meta
    return _make_response("funds_transfer", customer_id, extra)


def initiate_card_activation_with_issuer(
    customer_id: Optional[int],
    card_id: Optional[int],
    card_last4: Optional[str] = None,
    request_meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    extra: Dict[str, Any] = {"card_id": card_id, "card_last4": card_last4}
    if request_meta:
        extra["client_meta"] = request_meta
    return _make_response("card_activation", customer_id, extra)


def request_card_pin_change_via_issuer(
    customer_id: Optional[int],
    card_id: Optional[int],
    method: str = "sms",
    request_meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    extra: Dict[str, Any] = {"card_id": card_id, "method": method}
    if request_meta:
        extra["client_meta"] = request_meta
    return _make_response("card_pin_change", customer_id, extra)


def fetch_real_time_balance_from_core(
    customer_id: Optional[int],
    account_number: str,
    request_meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    extra: Dict[str, Any] = {"account_masked": (account_number[-6:] if account_number and len(account_number) > 6 else account_number)}
    if request_meta:
        extra["client_meta"] = request_meta
    return _make_response("real_time_balance", customer_id, extra)


def initiate_gateway_transfer(
    customer_id: Optional[int],
    from_account: str,
    to_account: str,
    amount: float,
    provider: str = "PAYGW",
    schedule_date: Optional[str] = None,
    request_meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    
    extra: Dict[str, Any] = {
        "provider": provider,
        "from_account_masked": (from_account[-6:] if from_account and len(from_account) > 6 else from_account),
        "to_account_masked": (to_account[-6:] if to_account and len(to_account) > 6 else to_account),
        "amount": float(amount),
        "schedule_date": schedule_date
    }
    if request_meta:
        extra["client_meta"] = request_meta
    return _make_response("gateway_transfer", customer_id, extra)


def lookup_card_issuer_status(card_last6: str) -> Dict[str, Any]:
    extra: Dict[str, Any] = {"card_last6": card_last6}
    return _make_response("card_issuer_lookup", None, extra)

def external_integration_placeholder(action_name: str, customer_id: Optional[int] = None, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    extra: Optional[Dict[str, Any]] = details.copy() if details else None
    return _make_response(action_name, customer_id, extra)
