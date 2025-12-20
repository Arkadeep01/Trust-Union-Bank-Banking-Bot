from security.masking import mask_phone, mask_email, mask_account

def sanitize_bot_response(text: str) -> str:
    if not text:
        return text

    # naive patterns (can be extended)
    if "@" in text:
        text = mask_email(text)
    if any(c.isdigit() for c in text):
        text = text.replace(text, mask_account(text))

    return text
