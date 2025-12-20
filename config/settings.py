import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV = os.getenv("ENVIRONMENT", "development")

# Load env
env_file = BASE_DIR / "config" / "env" / f".env.{ENV}"
if env_file.exists():
    load_dotenv(env_file)

# -----------------------------
# JWT (RS256)
# -----------------------------
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "RS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 14))

PRIVATE_KEY_PATH = BASE_DIR / "config/jwt_keys/private_key.pem"
PUBLIC_KEY_PATH  = BASE_DIR / "config/jwt_keys/public_key.pem"

# -----------------------------
# DATABASE
# -----------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

# -----------------------------
# EMAIL
# -----------------------------
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# -----------------------------
# FEATURES
# -----------------------------
ENABLE_SENTIMENT = os.getenv("ENABLE_SENTIMENT", "true").lower() == "true"
ENABLE_VOICE = os.getenv("ENABLE_VOICE", "true").lower() == "true"
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")

# -----------------------------
# VALIDATION
# -----------------------------
def validate_settings():
    errors = []

    if JWT_ALGORITHM != "RS256":
        errors.append("JWT_ALGORITHM must be RS256")

    if not PRIVATE_KEY_PATH.exists():
        errors.append("Missing private_key.pem")

    if not PUBLIC_KEY_PATH.exists():
        errors.append("Missing public_key.pem")

    if not DATABASE_URL:
        errors.append("DATABASE_URL not set")

    if errors:
        raise RuntimeError("CONFIG ERROR:\n" + "\n".join(errors))

validate_settings()
