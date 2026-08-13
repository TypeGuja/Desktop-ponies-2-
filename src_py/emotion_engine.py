# src_py/emotion_engine.py
import sys
from typing import Optional, List


class EmotionEngine:
    def __init__(self):
        self.classifier = None
        self._checked = False
        self._emotion_keywords = {
            "happy": ["happy", "glad", "joy", "wonderful", "great", "awesome",
                      "yay", "woohoo", "love", "beautiful", "friend", "fun"],
            "sad": ["sad", "cry", "miss", "alone", "lonely", "sorry", "goodbye",
                    "lost", "hurt", "pain", "tear", "wish"],
            "angry": ["angry", "mad", "furious", "grr", "buck off", "stupid",
                      "hate", "annoying", "ugh", "worst"],
            "surprised": ["wow", "what", "oh", "whoa", "omg", "incredible",
                          "amazing", "surprise", "unexpected", "really"],
            "nervous": ["nervous", "scared", "afraid", "worry", "anxious",
                        "eek", "help", "danger", "run"],
            "loving": ["love", "hug", "cuddle", "sweet", "dear", "darling",
                       "adorable", "precious", "care"],
        }

    def is_available(self) -> bool:
        if self._checked:
            return self.classifier is not None
        self._checked = True

        try:
            from transformers import pipeline
            self.classifier = pipeline(
                "text-classification",
                model="bhadresh-savani/distilbert-base-uncased-emotion",
                top_k=1,
            )
            print("[EMO] Transformer emotion classifier loaded", file=sys.stderr)
            return True
        except Exception as e:
            print(f"[EMO] Transformer not available: {e}", file=sys.stderr)
            print("[EMO] Using keyword-based classification", file=sys.stderr)
            return False

    def classify(self, text: str) -> str:
        if self.classifier:
            try:
                result = self.classifier(text[:512])[0]
                label = result[0]["label"]
                emotion_map = {
                    "joy": "happy",
                    "sadness": "sad",
                    "anger": "angry",
                    "surprise": "surprised",
                    "fear": "nervous",
                    "love": "loving",
                }
                return emotion_map.get(label, "neutral")
            except Exception as e:
                print(f"[EMO] Classification error: {e}", file=sys.stderr)

        return self._keyword_classify(text)

    def _keyword_classify(self, text: str) -> str:
        text_lower = text.lower()
        scores = {}
        for emotion, keywords in self._emotion_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[emotion] = score

        if scores:
            return max(scores, key=scores.get)
        return "neutral"

    def suggest_action(self, emotion: str, available_actions: List[str],
                       text: str) -> Optional[str]:
        text_lower = text.lower()

        # Явные команды в тексте имеют приоритет
        action_keywords = {
            "buck": ["buck", "kick", "buck off"],
            "rear": ["rear", "stand up", "rise"],
            "sleep": ["sleep", "tired", "nap", "rest"],
            "conga": ["dance", "conga", "party", "celebrate"],
            "pose": ["pose", "look", "pretty", "show off"],
            "gallop": ["run", "gallop", "fast", "race"],
            "walk": ["walk", "go", "move", "come", "trot"],
        }

        for action, keywords in action_keywords.items():
            if action in available_actions and any(kw in text_lower for kw in keywords):
                return action

        # Действия по эмоции
        emotion_actions = {
            "happy": ["pose", "conga", "walk"],
            "sad": ["sleep", "idle"],
            "angry": ["rear", "buck"],
            "surprised": ["rear"],
            "nervous": ["idle", "walk"],
            "loving": ["pose"],
        }

        suggested = emotion_actions.get(emotion, ["idle"])
        for action in suggested:
            if action in available_actions:
                return action

        return None