import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    def __init__(self, model_path: Optional[Path] = None):
        self.model = None
        self.tokenizer = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        if model_path is None:
            base_dir = Path(__file__).parent
            model_path = base_dir / "model" / "distilbert_sentiment" / "checkpoint-1168"

        self.model_path = model_path
        self._load_model()

    def _load_model(self):
        try:
            if not self.model_path.exists():
                logger.warning("Sentiment model not found, using rule-based fallback.")
                return

            self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_path))
            self.model = AutoModelForSequenceClassification.from_pretrained(str(self.model_path))
            self.model.to(self.device)
            self.model.eval()
            logger.info("✅ Sentiment model loaded successfully")
        except Exception as e:
            logger.exception("❌ Failed to load sentiment model, fallback enabled")
            self.model = None
            self.tokenizer = None

    # =================================================
    # ✅ PUBLIC API (EXPECTED BY ORCHESTRATOR)
    # =================================================
    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Public method used by ResponseOrchestrator
        """
        return self._analyze_internal(text)

    def _analyze_internal(self, text: str) -> Dict[str, Any]:
        if not text or not text.strip():
            return self._neutral()

        if self.model and self.tokenizer:
            try:
                inputs = self.tokenizer(
                    text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=256,
                    padding=True,
                ).to(self.device)

                with torch.no_grad():
                    outputs = self.model(**inputs)
                    probs = torch.softmax(outputs.logits, dim=-1)
                    idx = int(torch.argmax(probs, dim=-1))
                    score = float(probs[0][idx])

                labels = ["negative", "neutral", "positive"]
                label = labels[idx] if idx < len(labels) else "neutral"

                return {
                    "label": label,
                    "score": score,
                    "is_negative": label == "negative",
                    "is_frustrated": label == "negative" and score > 0.7,
                }
            except Exception:
                logger.exception("Model inference failed, using fallback")

        return self._fallback_sentiment(text)

    def _fallback_sentiment(self, text: str) -> Dict[str, Any]:
        text = text.lower()

        negative = [
            "angry", "frustrated", "worst", "hate", "problem", "issue",
            "error", "failed", "broken", "not working", "delay", "complaint"
        ]
        positive = [
            "thanks", "thank", "good", "great", "excellent", "happy", "love"
        ]

        neg = sum(1 for w in negative if w in text)
        pos = sum(1 for w in positive if w in text)

        if neg > pos:
            return {
                "label": "negative",
                "score": min(0.9, 0.5 + neg * 0.1),
                "is_negative": True,
                "is_frustrated": neg >= 2,
            }
        if pos > neg:
            return {
                "label": "positive",
                "score": min(0.9, 0.5 + pos * 0.1),
                "is_negative": False,
                "is_frustrated": False,
            }

        return self._neutral()

    def _neutral(self) -> Dict[str, Any]:
        return {
            "label": "neutral",
            "score": 0.5,
            "is_negative": False,
            "is_frustrated": False,
        }


# =================================================
# Singleton accessor
# =================================================
_sentiment_analyzer: Optional[SentimentAnalyzer] = None


def get_sentiment_analyzer() -> SentimentAnalyzer:
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer()
    return _sentiment_analyzer
