# core/utils/text_corrector.py
import os
import re
import json
import requests
from difflib import get_close_matches
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


COMMON_TYPOS = {
    "balnce": "balance",
    "balanc": "balance",
    "blnc": "balance",
    "trasfer": "transfer",
    "transfr": "transfer",
    "tranfer": "transfer",
    "statemnt": "statement",
    "sttmnt": "statement",
    "transction": "transaction",
    "trnsaction": "transaction",
    "withdrwal": "withdrawal",
    "withdrwl": "withdrawal",
    "accnt": "account",
    "acnt": "account",
    "benificiary": "beneficiary",
    "benficiary": "beneficiary",
    "amonut": "amount",
    "amout": "amount",
}

BANK_ABBREVIATIONS = {
    "amt": "amount",
    "amnt": "amount",
    "bal": "balance",
    "blnc": "balance",
    "acc": "account",
    "a/c": "account",
    "ac": "account",
    "txn": "transaction",
    "txns": "transactions",
    "stmt": "statement",
    "stmnt": "statement",
    "id": "identity",
    "kyc": "kyc",
}

DOMAIN_VOCAB = list({
    "balance", "amount", "transaction", "transfer", "statement",
    "account", "withdrawal", "beneficiary", "document", "emi",
    "interest", "deposit", "branch", "card", "limit", "fraud",
    "kyc", "password", "pin", "upi", "cheque", "number", "mobile",
    "email", "credit", "debit", "loan", "payment", "id"
})

VOWEL_CANDIDATES = ["a", "e", "i", "o", "u"]


def attempt_vowel_fill(word: str) -> List[str]:
    results = set()
    if any(v in word for v in VOWEL_CANDIDATES):
        return []
    for i in range(len(word) + 1):
        for v in VOWEL_CANDIDATES:
            candidate = word[:i] + v + word[i:]
            results.add(candidate)
    return list(results)


def clean_text_basic(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def fuzzy_fix(token: str) -> str:
    token = token or ""
    if token in COMMON_TYPOS:
        return COMMON_TYPOS[token]
    if token in BANK_ABBREVIATIONS:
        return BANK_ABBREVIATIONS[token]
    if len(token) >= 5:
        close = get_close_matches(token, DOMAIN_VOCAB, n=1, cutoff=0.78)
        if close:
            return close[0]
    if 3 <= len(token) <= 4:
        close = get_close_matches(token, DOMAIN_VOCAB, n=1, cutoff=0.60)
        if close:
            return close[0]
    vowel_attempts = attempt_vowel_fill(token)
    for guess in vowel_attempts:
        close = get_close_matches(guess, DOMAIN_VOCAB, n=1, cutoff=0.70)
        if close:
            return close[0]
    return token


def _build_gemini_prompt(user_text: str) -> str:
    return (
        "Correct the banking sentence. Fix spelling, expand abbreviations, "
        "preserve numbers but do NOT reveal sensitive info.\n"
        "Return ONLY the corrected sentence in lowercase.\n\n"
        f"User: {user_text}\nCorrected:"
    )



def call_llm_endpoint(prompt: str, timeout: int = 8) -> Optional[str]:

    url = os.getenv("LLM_API_URL")   # For gemini must contain the API key
    if not url:
        return None

    # Gemini-format request
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        if "candidates" in data:
            cand = data["candidates"][0]
            parts = cand.get("content", {}).get("parts", [])
            if parts and "text" in parts[0]:
                return parts[0]["text"].strip()

        return None

    except Exception:
        return None



def correct_typos_using_llm(text: str, timeout: int = 6) -> Optional[str]:
    use_llm = os.getenv("USE_LLM_CORRECTION", "false").lower() in ("1", "true", "yes")
    if not use_llm:
        return None

    prompt = _build_gemini_prompt(text)
    corrected = call_llm_endpoint(prompt, timeout=timeout)
    if not corrected:
        return None
    return clean_text_basic(corrected)



def correct_typos(text: str) -> str:
    text = text or ""

    llm_result = correct_typos_using_llm(text)
    if llm_result:
        return llm_result

    clean = clean_text_basic(text)
    tokens = clean.split()
    corrected = [fuzzy_fix(t) for t in tokens]
    return " ".join(corrected)
