# database/user/document_db.py
import os
import io
from typing import Optional
from datetime import datetime, timedelta
from database.core.db import run_query
from security.audit import record_audit
from auth.utils.email_service import send_email  
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def store_user_document(customer_id: int, doc_type: str, content: str) -> Optional[int]:
    base_dir = "/secure_uploads"
    user_dir = os.path.join(base_dir, str(customer_id))
    _ensure_dir(user_dir)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_name = f"{doc_type}_{timestamp}.txt"
    file_path = os.path.join(user_dir, safe_name)

    try:
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(content)

        q = """
            INSERT INTO kyc_docs (customer_id, doc_type, file_path, uploaded_at)
            VALUES (%s, %s, %s, NOW())
            RETURNING kyc_id;
        """
        res = run_query(q, (customer_id, doc_type, file_path), fetch=True)

        # Use customer_id as the actor who performed the upload
        record_audit("kyc_docs", customer_id, "upload", customer_id, {
            "doc_type": doc_type,
            "file_path": file_path
        })

        return res[0]["kyc_id"] if res else None

    except Exception as e:
        # Prefer customer_id as actor; if not applicable use 0 (system)
        record_audit("kyc_docs", customer_id, "upload_failed", customer_id, {"error": str(e)})
        return None


def _build_statement_pdf(customer_id: int, output_path: str, period_days: int = 30) -> bool:
    q = """
        SELECT transaction_reference, timestamp, sender_account_number, receiver_account_number,
               amount, txn_type, status, description
        FROM transactions
        WHERE customer_id = %s
          AND timestamp >= (NOW() - INTERVAL '%s days')
        ORDER BY timestamp DESC
        LIMIT 500
    """
    rows = run_query(q, (customer_id, period_days), fetch=True) or []

    try:
        _ensure_dir(os.path.dirname(output_path))
        c = canvas.Canvas(output_path, pagesize=A4)
        width, height = A4

        margin = 15 * mm
        y = height - margin

        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y, f"Trust Union Bank - Account Statement (last {period_days} days)")
        y -= 10 * mm

        c.setFont("Helvetica", 10)
        c.drawString(margin, y, f"Customer ID: {customer_id}")
        c.drawString(width/2, y, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        y -= 8 * mm

        # Table header
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin, y, "Date")
        c.drawString(margin + 70*mm, y, "Description / Ref")
        c.drawString(margin + 140*mm, y, "Amount")
        y -= 6 * mm
        c.setFont("Helvetica", 9)

        if not rows:
            c.drawString(margin, y, "No transactions in this period.")
            c.showPage()
            c.save()
            return True

        for r in rows:
            if y < margin + 20:
                c.showPage()
                y = height - margin

            ts = r.get("timestamp")
            ts_str = ts.strftime("%Y-%m-%d") if ts else "-"
            desc = (r.get("description") or r.get("transaction_reference") or "")[:60]
            amt = r.get("amount") or 0.0

            c.drawString(margin, y, ts_str)
            c.drawString(margin + 70*mm, y, desc)
            c.drawRightString(margin + 200*mm, y, f"₹{float(amt):,.2f}")
            y -= 6 * mm

        c.showPage()
        c.save()
        return True

    except Exception as e:
        # Use customer_id as the actor when logging the failure
        record_audit("statements", customer_id, "pdf_generation_failed", customer_id, {"error": str(e)})
        return False


def generate_statement_pdf_link(customer_id: int, period_days: int = 30) -> Optional[str]:
    base_storage = "/secure_uploads"
    user_dir = os.path.join(base_storage, str(customer_id), "statements")
    _ensure_dir(user_dir)

    filename = f"statement_{period_days}d_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.pdf"
    file_path = os.path.join(user_dir, filename)

    ok = _build_statement_pdf(customer_id, file_path, period_days=period_days)
    if not ok:
        # Log failure with customer_id as actor
        record_audit("statements", customer_id, "generate_pdf_failed", customer_id, {"file_path": file_path})
        return None

    # Audit success using customer_id as performer
    record_audit("statements", customer_id, "generate_pdf", customer_id, {"file_path": file_path})

    public_base = "https://trustunionbank.com/secure_statements"  
    public_url = f"{public_base}/{customer_id}/{os.path.basename(file_path)}"
    return public_url


def send_statement_via_email(customer_id: int, period_days: int = 30) -> bool:
    q = "SELECT email FROM users WHERE customer_id = %s"
    rows = run_query(q, (customer_id,), fetch=True)
    if not rows:
        record_audit("statements", customer_id, "email_statement_failed", customer_id, {"reason": "no_email"})
        return False

    email = rows[0].get("email")
    if not email:
        record_audit("statements", customer_id, "email_statement_failed", customer_id, {"reason": "empty_email"})
        return False

    base_storage = "/secure_uploads"
    user_dir = os.path.join(base_storage, str(customer_id), "statements")
    _ensure_dir(user_dir)
    filename = f"statement_{period_days}d_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.pdf"
    file_path = os.path.join(user_dir, filename)

    ok = _build_statement_pdf(customer_id, file_path, period_days=period_days)
    if not ok:
        record_audit("statements", customer_id, "pdf_generation_failed", customer_id, {"file_path": file_path})
        return False

    subject = "Your Account Statement - Trust Union Bank"
    # Use HTML for rich content; plain text fallback provided too.
    html_body = (
        "<p>Dear customer,</p>"
        "<p>Please find attached your account statement. For security reasons, this file is confidential.</p>"
        "<p>— Trust Union Bank</p>"
    )
    plain_body = "Please find attached your account statement. For security reasons, this file is confidential."

    try:
        # Correct call: use new parameter names (to_email, html_body, plain_body, attachments)
        send_ok = False
        try:
            send_ok = send_email(
                to_email=email,
                subject=subject,
                html_body=html_body,
                plain_body=plain_body,
                attachments=[file_path],
            )
        except TypeError:
            # Fallback for an older send_email signature that only accepted positional args:
            # send_email(email, subject, html_body) -> still works
            send_ok = send_email(email, subject, html_body + f"\n\nDownload: {generate_statement_pdf_link(customer_id, period_days)}")

        record_audit("statements", customer_id, "email_statement", customer_id, {
            "sent_to": email,
            "file_path": file_path,
            "status": bool(send_ok)
        })
        return bool(send_ok)
    except Exception as e:
        record_audit("statements", customer_id, "email_statement_failed", customer_id, {"error": str(e)})
        return False
