from typing import Callable, Dict, Any, Optional, List

def _import_services():
    role_service = None
    auth_service = None
    otp_service = None

    try:
        from database.services import role_service, auth_service, otp_service
    except Exception:
        pass

    user_db = None
    document_db = None
    branch_db = None
    agent_db = None

    try:
        from database.user import user_db, document_db, branch_db, agent as agent_db
    except Exception:
        pass

    return {
        "role_service": role_service,
        "auth_service": auth_service,
        "otp_service": otp_service,
        "user_db": user_db,
        "document_db": document_db,
        "branch_db": branch_db,
        "agent_db": agent_db,
    }


_SERVICES = _import_services()

# -------------------------------------------------
# Registry
# -------------------------------------------------
FUNCTION_REGISTRY: Dict[str, Callable[..., Any]] = {}


def _register_defaults():
    svc = _SERVICES

    if svc.get("user_db"):
        try:
            FUNCTION_REGISTRY["fetch_user_accounts"] = svc["user_db"].get_user_accounts
            FUNCTION_REGISTRY["get_user_by_customer_id"] = svc["user_db"].get_user_by_customer_id
        except Exception:
            pass

    if svc.get("document_db"):
        try:
            FUNCTION_REGISTRY["send_statement_email"] = svc["document_db"].send_statement_via_email
            FUNCTION_REGISTRY["generate_statement_pdf_link"] = svc["document_db"].generate_statement_pdf_link
        except Exception:
            pass

    if svc.get("branch_db"):
        try:
            FUNCTION_REGISTRY["find_branches_by_location"] = svc["branch_db"].get_branch_by_location
            FUNCTION_REGISTRY["get_branch_by_code"] = svc["branch_db"].get_branch_by_code
            FUNCTION_REGISTRY["get_all_branches"] = svc["branch_db"].get_all_branches
        except Exception:
            pass

    if svc.get("otp_service"):
        try:
            FUNCTION_REGISTRY["generate_otp"] = svc["otp_service"].generate_otp
            FUNCTION_REGISTRY["verify_otp"] = svc["otp_service"].verify_otp
        except Exception:
            pass


_register_defaults()


def list_registered_functions() -> List[str]:
    return sorted(FUNCTION_REGISTRY.keys())


def get_callable(name: str) -> Optional[Callable[..., Any]]:
    return FUNCTION_REGISTRY.get(name)


def dispatch_function(name: str, params: Optional[dict] = None) -> Any:
    fn = get_callable(name)
    if not fn:
        raise KeyError(f"Function not allowed or not registered: {name}")

    params = params or {}
    if not isinstance(params, dict):
        raise ValueError("params must be a dict")

    return fn(**params)
