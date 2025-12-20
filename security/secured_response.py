from security.sanitizer import sanitize_bot_response

SENSITIVE_KEYWORDS = [
    "otp",
    "pin",
    "password",
    "cvv",
    "secret",
]

def secure_bot_output(text: str) -> str:
    lowered = text.lower()

    for word in SENSITIVE_KEYWORDS:
        if word in lowered:
            return (
                "For security reasons, I can’t share sensitive information here. "
                "Please continue via secure authentication."
            )

    return sanitize_bot_response(text)
