import re

def mask_phone(phone: str) -> str:
    if not phone:
        return phone
    return re.sub(r"\d(?=\d{4})", "*", phone)

def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return email
    name, domain = email.split("@", 1)
    return name[0] + "***@" + domain

def mask_account(acc: str) -> str:
    if not acc:
        return acc
    return "****" + acc[-4:]

def mask_otp(_: str) -> str:
    return "******"
