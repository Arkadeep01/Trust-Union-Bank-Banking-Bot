from typing import Any, Dict, List, Text
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import requests
import os
import logging

LOG = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


class ActionBackendBridge(Action):
    def name(self) -> Text:
        return "action_backend_bridge"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        latest = tracker.latest_message

        intent = latest.get("intent", {}).get("name")
        entities = latest.get("entities", [])
        text = latest.get("text")
        metadata = latest.get("metadata", {}) or {}

        payload = {
            "intent": intent,
            "entities": entities,
            "text": text,
            "customer_id": metadata.get("customer_id"),
            "lang": metadata.get("lang", "en"),
            "sender_id": tracker.sender_id,
        }

        try:
            resp = requests.post(
                f"{BACKEND_URL}/api/internal/rasa-bridge",
                json=payload,
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()

        except Exception as e:
            LOG.exception("Backend bridge failure")
            dispatcher.utter_message(
                text="⚠️ Service temporarily unavailable. Please try again later."
            )
            return []

        # 🔒 ABSOLUTE RULE: DO NOT MODIFY RESPONSE
        bot_response = data.get("bot_response")
        if bot_response:
            dispatcher.utter_message(text=bot_response)
        else:
            dispatcher.utter_message(
                text="⚠️ Unable to process your request at the moment."
            )

        return []
