# core/utils/voice_i18n.py
import re
import logging
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

import requests
from langdetect import detect as langdetect_detect
from gtts import gTTS
import speech_recognition as sr
import pyttsx3

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
 
root_dir = Path(__file__).resolve().parent.parent.parent
env_path = root_dir / ".env"

load_dotenv(dotenv_path=env_path)
load_dotenv()

USE_LLM_TRANSLATION = os.getenv("USE_LLM_TRANSLATION", "false").lower() in ("1", "true", "yes")
LLM_API_URL = os.getenv("LLM_API_URL")  
LLM_API_KEY = os.getenv("LLM_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
DEFAULT_LANG = os.getenv("DEFAULT_LANGUAGE", "en")

SUPPORTED_LANGS = {"en", "hi", "bn"}


# -------------------- Language Detection (informational only) --------------------
def detect_language(text: str) -> str:
    if not text or not text.strip():
        return DEFAULT_LANG
    try:
        return langdetect_detect(text)
    except Exception:
        pass

    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    if re.search(r"[\u0980-\u09FF]", text):
        return "bn"

    return DEFAULT_LANG


# -------------------- GEMINI TRANSLATION (CORRECT FORMAT) --------------------
def _translate_via_llm(text: str, tgt: str, timeout: int = 10) -> Optional[str]:
    """
    Groq API translator using OpenAI-compatible chat completions.
    """
    if not USE_LLM_TRANSLATION or not LLM_API_URL or not LLM_API_KEY:
        LOG.warning("Translation backend misconfigured.")
        return None

    # Groq Payload Format
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": f"You are a helpful assistant that translates text to {tgt}. Return ONLY the translated text and nothing else."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "temperature": 0.2
    }

    try:
        resp = requests.post(
            LLM_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LLM_API_KEY}"
            },
            json=payload,
            timeout=timeout,
        )
        
        if resp.status_code == 429:
            LOG.error("Groq Quota Exceeded (429).")
            return None
            
        resp.raise_for_status()
        data = resp.json()

        # Parse OpenAI-style response
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()

        LOG.error("Groq response format not recognized: %s", data)

    except Exception:
        LOG.exception("Groq translation failed")

    return None

# -------------------- Unified Translation API --------------------
def translate_text(text: str, tgt: str) -> str:
    if not text or tgt not in SUPPORTED_LANGS:
        return text

    if not USE_LLM_TRANSLATION:
        LOG.warning("Translation skipped: USE_LLM_TRANSLATION is set to False")
        return text
    
    if not LLM_API_URL:
        LOG.warning("Translation skipped: LLM_API_URL is not set")
        return text

    translated = _translate_via_llm(text, tgt)
    if translated:
        return translated

    return text


# -------------------- Speech Recognition --------------------
def listen_for_query(timeout: float = 5.0, prefer_lang: Optional[str] = None) -> Optional[str]:
    if sr is None:
        LOG.warning("SpeechRecognition not available")
        return None

    recognizer = sr.Recognizer()
    recog_lang = "en-US"

    if prefer_lang == "hi":
        recog_lang = "hi-IN"
    elif prefer_lang == "bn":
        recog_lang = "bn-BD"

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=timeout)

        return recognizer.recognize_google(  # type: ignore[attr-defined]
            audio,
            language=recog_lang
        )
    except Exception:
        LOG.exception("Speech recognition failed")
        return None


# -------------------- Text-to-Speech --------------------
def speak_response(text: str, lang_code: Optional[str] = None):
    clean = re.sub(r"<[^>]+>", "", text or "").strip()
    if not clean:
        return

    if lang_code in ("hi", "bn"):
        try:
            tts = gTTS(text=clean, lang=lang_code)
            path = os.path.join(os.getcwd(), "bankbot_tts.mp3")
            tts.save(path)
            return
        except Exception:
            LOG.warning("gTTS failed; falling back to pyttsx3")

    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 150)
        engine.say(clean)
        engine.runAndWait()
    except Exception:
        LOG.exception("TTS failed")


# -------------------- CLI TEST HARNESS --------------------
if __name__ == "__main__":
    print("\n=============== Voice Language & Multilingual Test ===============\n")
    print("Choose output language (input can be ANY language)")
    print("1. English (en)")
    print("2. Hindi   (hi)")
    print("3. Bengali (bn)")
    print("4. Exit")
    print("=================================================================\n")

    choice_map = {"1": "en", "2": "hi", "3": "bn"}

    while True:
        raw = input(
            "Enter the Language you want to translate your text "
            "or (Enter 4 or 'exit') to quit: "
        ).strip().lower()

        if raw in ("4", "exit"):
            print("Exiting test.")
            break

        choice = choice_map.get(raw, raw)
        if choice not in SUPPORTED_LANGS:
            print("❌ Invalid choice.\n")
            continue

        user_text = input("Enter text (any language): ").strip()
        if not user_text:
            print("Empty input.\n")
            continue

        auto_lang = detect_language(user_text)
        print(f"Detected language (auto): {auto_lang}")
        print(f"Target language (user):  {choice}")

        translated = translate_text(user_text, tgt=choice)
        print(f"(auto → {choice})")
        print(f"Translated Text: {translated}")

        speak = input("Speak the translated text? (y/n): ").strip().lower()
        if speak == "y":
            speak_response(translated, choice)
            print("Done.\n")
        else:
            print("Skipped speech.\n")
