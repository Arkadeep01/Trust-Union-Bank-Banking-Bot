from auth.db_adapter import (
    find_user_by_email,
    find_user_by_phone,
    find_customer_by_account_number,
)
from auth.utils.otp_manager import generate_login_otp, verify_login_otp
from auth.authentication.token_manager import token_manager

def resolve_identifier(identifier: str):
    if "@" in identifier:
        return find_user_by_email(identifier)
    if identifier.isdigit():
        return find_customer_by_account_number(identifier) or find_user_by_phone(identifier)
    return None

def login_start(identifier: str):
    user = resolve_identifier(identifier)
    if not user:
        return {"success": False, "reason": "user_not_found"}

    generate_login_otp(
        customer_id=user["customer_id"],
        name=user["name"],
        email=user["email"],
    )
    return {"success": True, "customer_id": user["customer_id"]}

def login_verify(customer_id: int, otp: str):
    if not verify_login_otp(customer_id, otp):
        return {"success": False, "reason": "invalid_otp"}

    return {
        "success": True,
        "access_token": token_manager.create_access_token(customer_id),
        "refresh_token": token_manager.create_refresh_token(customer_id),
    }
