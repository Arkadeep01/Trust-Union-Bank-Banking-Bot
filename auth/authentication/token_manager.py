import jwt
from datetime import datetime, timedelta
from typing import Dict

from config.settings import (
    PRIVATE_KEY_PATH,
    PUBLIC_KEY_PATH,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

# Load keys ONCE from validated config paths
PRIVATE_KEY = PRIVATE_KEY_PATH.read_text()
PUBLIC_KEY = PUBLIC_KEY_PATH.read_text()

ISSUER = "trust-union-bank"
AUDIENCE = "trust-union-clients"


class TokenManager:
    def create_access_token(self, customer_id: int) -> str:
        now = datetime.utcnow()
        payload = {
            "sub": str(customer_id),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
            "iss": ISSUER,
            "aud": AUDIENCE,
            "type": "access",
        }
        return jwt.encode(payload, PRIVATE_KEY, algorithm=JWT_ALGORITHM)

    def create_refresh_token(self, customer_id: int) -> str:
        now = datetime.utcnow()
        payload = {
            "sub": str(customer_id),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()),
            "iss": ISSUER,
            "aud": AUDIENCE,
            "type": "refresh",
        }
        return jwt.encode(payload, PRIVATE_KEY, algorithm=JWT_ALGORITHM)

    def decode_token(self, token: str) -> Dict:
        try:
            return jwt.decode(
                token,
                PUBLIC_KEY,
                algorithms=[JWT_ALGORITHM],
                audience=AUDIENCE,
                issuer=ISSUER,
            )
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")


token_manager = TokenManager()
