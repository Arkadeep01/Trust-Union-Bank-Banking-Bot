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

## 1. Clone the Repository
```bash
git clone [https://github.com/Arkadeep01/Trust-Union-Bank-Banking-Bot.git](https://github.com/Arkadeep01/Trust-Union-Bank-Banking-Bot.git)
cd Trust-Union-Bank-Banking-Bot
```

## 2. Virtual Environment
### Windows
```bash
python -m venv venv
venv\Scripts\activate
```
### Linux / MacOS
```
python3 -m venv venv
source venv/bin/activate
```


## 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## 4. Environment Configuration
### Create a local .env file (not committed to Git):
```bash
cp .env.example .env
```
Edit .env and provide values such as:
- Database URL / credentials
- SMTP credentials
- JWT settings
- Rasa endpoint URL


## 5. JWT Key Management (REQUIRED)
#### JWT authentication uses RSA asymmetric keys.
### 📁 Required Directory Structure
```text
config/
├── jwt_keys/
│   ├── private_key.pem
│   └── public_key.pem
├── secrets.json
├── models.json
└── settings.py
```

1️⃣ Generate JWT Keys
```bash
mkdir -p config/jwt_keys

# Generate private key
openssl genrsa -out config/jwt_keys/private_key.pem 2048

# Generate public key
openssl rsa -in config/jwt_keys/private_key.pem -pubout -out config/jwt_keys/public_key.pem
```
2️⃣ Create config/secrets.json
```json
{
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
```
3️⃣ Create config/models.json
```json
{
  "sentiment_model": "distilbert-base-uncased",
  "intent_threshold": 0.65
}
```

## 🗄️ Database Setup
1. Create a PostgreSQL database.
2. Execute SQL files in order:
```text
schema.sql
schema_indexes.sql
```

## 🤖 Rasa Training & Execution
```bash
cd rasa
rasa train
cd ..
```

## ▶️ Run the Application
```bash
▶️ Run the Application
```

