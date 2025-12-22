# 🏦 Trust Union Bank – AI Banking Chatbot

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Rasa](https://img.shields.io/badge/Rasa-5A17EE?style=for-the-badge&logo=rasa)](https://rasa.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![JWT](https://img.shields.io/badge/JWT-black?style=for-the-badge&logo=JSON%20web%20tokens)](https://jwt.io/)

A **secure, sessionless, Rasa-driven banking chatbot** built using **FastAPI + Rasa + PostgreSQL**, designed with real-world backend, security, and enterprise-grade practices.

> [!IMPORTANT]
> This repository **intentionally excludes secrets, credentials, and trained ML models**. All sensitive or generated artifacts must be created **locally by each developer**.

---

## 🚀 Key Highlights

- 🤖 **Rasa-powered** conversational AI (NLU + dialogue via `domain.yml`)
- ⚡ **FastAPI backend** (high-performance, async)
- 🔐 **OTP + MPIN** authentication flows
- 🧠 **Sentiment-aware** chat handling
- 🏦 **Banking services** (accounts, balance, branches, loans, cards, complaints)
- 🧩 **Stateless design** (JWT-based)
- 🛡️ **Strong security** & audit logging
- ▶️ **Rasa auto-start** support with backend

---

## 🛠️ Prerequisites

Install the following before starting:
* **Python 3.9 – 3.11**
* **PostgreSQL** (or Supabase)
* **Rasa**
* **OpenSSL** (for JWT key generation)

---

## 📦 Installation & Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/Arkadeep01/Trust-Union-Bank-Banking-Bot.git](https://github.com/Arkadeep01/Trust-Union-Bank-Banking-Bot.git)
cd Trust-Union-Bank-Banking-Bot
2. Virtual Environment (Recommended)Bash# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
3. Install DependenciesBashpip install -r requirements.txt
4. Environment ConfigurationBashcp .env.example .env
# Edit .env and provide your DB and SMTP credentials
🔐 Security Configuration (Required)1. Generate JWT RSA KeysJWT signing uses asymmetric RSA keys. Create the directory and generate the keys:Bashmkdir -p config/jwt_keys

# Generate private key
openssl genrsa -out config/jwt_keys/private_key.pem 2048

# Generate public key
openssl rsa -in config/jwt_keys/private_key.pem -pubout -out config/jwt_keys/public_key.pem
2. Create Local Config FilesCreate these files in the config/ directory (they are ignored by Git):config/secrets.jsonJSON{
  "jwt": {
    "algorithm": "RS256",
    "access_token_exp_minutes": 15,
    "refresh_token_exp_days": 7
  },
  "security": {
    "otp_length": 6,
    "otp_expiry_minutes": 5,
    "max_otp_attempts": 3
  }
}
config/models.jsonJSON{
  "sentiment_model": "distilbert-base-uncased",
  "intent_threshold": 0.65
}
🗄️ Database SetupCreate a PostgreSQL database.Execute the SQL files in this order:schema.sqlschema_indexes.sql🤖 Training & ExecutionTrain the Rasa ModelRasa models are not stored in GitHub. You must train them locally:Bashcd rasa
rasa train
cd ..
Run the ApplicationFrom the project root:Bashpython -m api.api_server
Health Check: GET http://localhost:8000/api/healthFrontend: Open http://localhost:8000 in your browser.🛠️ TroubleshootingIssueSolutionRasa not foundRun pip install rasa inside your venv.ModuleNotFoundErrorEnsure you run the server from the root directory.JWT ErrorsVerify that private_key.pem exists in config/jwt_keys/.DB Connection RefusedCheck your .env credentials and Postgres status.🔒 Security NoticeThe following items are strictly ignored by .gitignore to ensure security:.env & .env.localconfig/jwt_keys/*.pemrasa/models/*.tar.gzconfig/secrets.json
