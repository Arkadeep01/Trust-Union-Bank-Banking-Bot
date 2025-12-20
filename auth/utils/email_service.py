# auth/utils/email_service.py
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formataddr
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_ADMIN_EMAIL = os.getenv("SMTP_ADMIN_EMAIL", SMTP_USER)

FROM_NAME = "Trust Union Bank"
FROM_EMAIL = SMTP_ADMIN_EMAIL


def send_email(
    to_email: Union[str, List[str]],
    subject: str,
    html_body: str,
    plain_body: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    from_name: Optional[str] = None,
    from_email: Optional[str] = None,
) -> bool:
    # runtime check
    if not all([SMTP_SERVER, SMTP_USER, SMTP_PASSWORD]):
        logger.error("SMTP config missing. Set SMTP_SERVER/SMTP_USER/SMTP_PASSWORD in env.")
        raise RuntimeError("SMTP config missing. Set SMTP_SERVER/SMTP_USER/SMTP_PASSWORD in env.")

    # static-type friendly assertions so linters know these are str
    assert SMTP_SERVER is not None
    assert SMTP_USER is not None
    assert SMTP_PASSWORD is not None

    # fallback plain body
    if plain_body is None:
        plain_body = html_body

    # normalize recipients
    if isinstance(to_email, str):
        recipients = [to_email]
    else:
        recipients = list(to_email)

    # sender info (coerce to str to satisfy formataddr type)
    sender_name = from_name or FROM_NAME
    sender_email = (from_email or FROM_EMAIL) or SMTP_USER or ""
    # ensure both are strings (formataddr expects (str, str))
    if sender_email is None:
        sender_email = ""
    if sender_name is None:
        sender_name = ""

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = formataddr((str(sender_name), str(sender_email)))
    msg["To"] = ", ".join(recipients)

    part1 = MIMEText(plain_body or "", "plain", _charset="utf-8")
    part2 = MIMEText(html_body or "", "html", _charset="utf-8")
    msg.attach(part1)
    msg.attach(part2)

    if attachments:
        for path in attachments:
            try:
                with open(path, "rb") as fh:
                    part = MIMEApplication(fh.read(), Name=os.path.basename(path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
                    msg.attach(part)
            except Exception as e:
                logger.exception("Failed to attach file %s: %s", path, e)
                continue

    # assign to locals (help static checkers)
    server_host: str = SMTP_SERVER
    server_port: int = SMTP_PORT
    smtp_user: str = SMTP_USER
    smtp_pass: str = SMTP_PASSWORD

    # final asserts for static type checkers
    assert isinstance(server_host, str)
    assert isinstance(smtp_user, str)
    assert isinstance(smtp_pass, str)

    try:
        with smtplib.SMTP(server_host, server_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(str(sender_email), recipients, msg.as_string())
        return True
    except Exception as e:
        logger.exception("Failed to send email to %s: %s", recipients, e)
        return False


def build_otp_email(to_name: str, otp_code: str, purpose: str):
    subject = f"Your {purpose} OTP — Trust Union Bank"
    html = f"""
    <html>
      <body>
        <p>Hi {to_name},</p>
        <p>Your OTP for <b>{purpose}</b> at Trust Union Bank is:</p>
        <h2 style="letter-spacing:4px">{otp_code}</h2>
        <p>This OTP will expire shortly. If you did not request this, contact support immediately.</p>
        <p>— Trust Union Bank</p>
      </body>
    </html>
    """
    text = f"Hi {to_name},\n\nYour OTP for {purpose} at Trust Union Bank is: {otp_code}\n\nThis OTP will expire shortly."
    return subject, html, text
