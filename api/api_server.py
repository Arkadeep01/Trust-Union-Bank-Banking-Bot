# api_server.py – Trust Union Bank Backend
# MODE: SESSIONLESS, RASA-DRIVEN RESPONSES

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import sys
import logging
import requests
import subprocess
import time
import atexit
from pathlib import Path
from dotenv import load_dotenv

# -------------------------------------------------
# ENV + PATH
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)

sys.path.insert(0, str(BASE_DIR))

# -------------------------------------------------
# BACKEND IMPORTS
# -------------------------------------------------

from database.core.connect import init_pool
from auth.authentication.primary_auth import login_start, login_verify
from auth.authentication.token_manager import token_manager
from database.user.user_db import get_user_by_customer_id, get_user_balance_from_db
from database.user.branch_db import get_all_branches, get_user_accounts
from intelligence.Sentiment_Analysis.Detect_Sentiment import get_sentiment_analyzer

# -------------------------------------------------
# LOGGING
# -------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trustunionbank")

# -------------------------------------------------
# DATABASE INIT
# -------------------------------------------------

try:
    init_pool()
    logger.info("✅ Database pool initialized")
except Exception as e:
    logger.warning("⚠️ Database init failed: %s", e)

# -------------------------------------------------
# RASA AUTO-START
# -------------------------------------------------

RASA_PROCESS = None
RASA_URL = os.getenv(
    "RASA_URL",
    "http://localhost:5005/webhooks/rest/webhook"
)

def start_rasa_server():
    global RASA_PROCESS

    if os.getenv("AUTO_START_RASA", "true").lower() not in ("1", "true", "yes"):
        logger.info("⚠️ AUTO_START_RASA disabled")
        return

    try:
        logger.info("🚀 Starting Rasa server...")

        RASA_PROCESS = subprocess.Popen(
            [
                "rasa",
                "run",
                "--enable-api",
                "--cors",
                "*",
                "--port",
                "5005",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Give Rasa time to boot
        time.sleep(6)

        logger.info("✅ Rasa server started")

    except FileNotFoundError:
        logger.error("❌ Rasa not found. Install with: pip install rasa")
    except Exception as e:
        logger.exception("❌ Failed to start Rasa: %s", e)

def stop_rasa_server():
    global RASA_PROCESS
    if RASA_PROCESS:
        logger.info("🛑 Stopping Rasa server...")
        RASA_PROCESS.terminate()
        try:
            RASA_PROCESS.wait(timeout=10)
        except Exception:
            pass

atexit.register(stop_rasa_server)

# 🔥 START RASA HERE (CRITICAL)
start_rasa_server()

# -------------------------------------------------
# APP + CORS
# -------------------------------------------------

ALLOWED_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app = FastAPI(
    title="Trust Union Bank API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# CORE OBJECTS
# -------------------------------------------------

sentiment_analyzer = get_sentiment_analyzer()

# -------------------------------------------------
# REQUEST MODELS
# -------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    lang: Optional[str] = "en"

class LoginRequest(BaseModel):
    identifier: str

class VerifyOTPRequest(BaseModel):
    customer_id: int
    otp_code: str

# -------------------------------------------------
# HEALTH
# -------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok"}

# -------------------------------------------------
# AUTH
# -------------------------------------------------

@app.post("/api/auth/login/start")
async def login_start_endpoint(request: LoginRequest):
    result = login_start(request.identifier)
    if result.get("success"):
        return result
    raise HTTPException(status_code=400, detail=result.get("reason"))

@app.post("/api/auth/login/verify")
async def login_verify_endpoint(request: VerifyOTPRequest):
    result = login_verify(request.customer_id, request.otp_code)
    if result.get("success"):
        return result
    raise HTTPException(status_code=401, detail=result.get("reason"))

# -------------------------------------------------
# CHAT (RASA FULLY OWNS RESPONSE)
# -------------------------------------------------

@app.post("/api/chat")
async def chat_endpoint(
    request: ChatRequest,
    authorization: Optional[str] = Header(None),
):
    try:
        customer_id: Optional[int] = None

        # JWT (optional)
        if authorization:
            token = authorization.replace("Bearer ", "")
            payload = token_manager.decode_token(token)
            sub = payload.get("sub")
            if sub is not None:
                customer_id = int(sub)

        # Sentiment
        sentiment = sentiment_analyzer.analyze(request.message)

        # Forward to Rasa
        rasa_payload = {
            "sender": f"user_{customer_id or 'guest'}",
            "message": request.message,
            "metadata": {
                "customer_id": customer_id,
                "lang": request.lang,
                "sentiment": sentiment,
            },
        }

        rasa_response = requests.post(
            RASA_URL,
            json=rasa_payload,
            timeout=10,
        )
        rasa_response.raise_for_status()

        rasa_messages = rasa_response.json()

        if isinstance(rasa_messages, list) and rasa_messages:
            return {
                "bot_response": rasa_messages[0].get("text", ""),
                "lang": request.lang,
            }

        return {
            "bot_response": "Sorry, I didn’t understand that.",
            "lang": request.lang,
        }

    except Exception:
        logger.exception("❌ Chat error")
        raise HTTPException(
            status_code=500,
            detail="Chat processing failed",
        )

# -------------------------------------------------
# USER APIs (DIRECT DB)
# -------------------------------------------------

@app.get("/api/user/profile")
async def get_profile(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    payload = token_manager.decode_token(token)

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = get_user_by_customer_id(int(sub))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user

@app.get("/api/user/accounts")
async def get_accounts(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    payload = token_manager.decode_token(token)

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {"accounts": get_user_accounts(int(sub))}

@app.get("/api/user/balance")
async def get_balance(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    payload = token_manager.decode_token(token)

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {"balance": get_user_balance_from_db(int(sub))}

@app.get("/api/branches")
async def branches():
    return {"branches": get_all_branches()}

# -------------------------------------------------
# FRONTEND
# -------------------------------------------------

static_dir = BASE_DIR / "frontend/static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    index = BASE_DIR / "frontend/pages/index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse("Frontend not found")

# -------------------------------------------------
# RUN
# -------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    import platform

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    ENV = os.getenv("ENVIRONMENT", "development")

    logger.info("🚀 Trust Union Bank API running on %s:%s", HOST, PORT)

    if ENV == "production" and not platform.system().lower().startswith("win"):
        uvicorn.run(app, host=HOST, port=PORT, workers=1)
    else:
        uvicorn.run(app, host=HOST, port=PORT, log_level="debug")
