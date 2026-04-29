# src_py/rule_engine.py
import random
import sys
from typing import Dict, Any, List, Optional


class RuleEngine:
    """Рул-бейз движок — работает всегда, без моделей"""

    def __init__(self):
        self._init_responses()

    def _init_responses(self):
        # Шаблоны ответов по ситуациям
        self.greetings = [
            "{action} Hi there, {user}!",
            "{action} Hey! Great to see you!",
            "{action} Hello! Nice day, isn't it?",
            "{action} *trots over happily* Hi!",
            "{action} *ears perk up* Oh, hello!",
        ]

        self.idle_thoughts = [
            "{action} *looks around the desktop*",
            "{action} What a lovely day!",
            "{action} *hums a little tune*",
            "{action} *swishes tail* Hmm...",
            "{action} I wonder what {other_pony} is doing?",
            "{action} *grazes on some desktop icons*",
            "{action} *stretches wings* (if pegasus)",
            "{action} *practices magic* (if unicorn)",
            "{action} La la la...",
            "{action} *counts desktop windows*",
        ]

        self.reactions_to_user = [
            "{action} You're funny!",
            "{action} *tilts head* Really?",
            "{action} That's interesting!",
            "{action} *nods approvingly*",
            "{action} Tell me more!",
            "{action} *giggles* You're silly!",
            "{action} I like you!",
            "{action} *stomps hoof* I agree!",
        ]

        self.interactions = [
            "{action} *nuzzles {other_pony}* Hey!",
            "{action} *trots alongside {other_pony}*",
            "{action} Let's play, {other_pony}!",
            "{action} *whinnies at {other_pony}*",
            "{action} *shares apple with {other_pony}*",
            "{action} Race you to the recycle bin!",
        ]

        self.emotion_actions = {
            "happy": ["*bounces*", "*skips*", "*beams*", "*giggles*"],
            "sad": ["*sighs*", "*ears droop*", "*sniffles*", "*looks down*"],
            "angry": ["*stomps*", "*snorts*", "*glowers*", "*flicks tail*"],
            "surprised": ["*gasps*", "*eyes widen*", "*jumps*", "*startled*"],
            "nervous": ["*shuffles hooves*", "*glances around*", "*ears flatten*"],
            "loving": ["*nuzzles*", "*hugs*", "*nuzzles affectionately*", "*warm smile*"],
        }

    def generate(self, request_type: str, text: str, pony_name: str,
                 personality: str, pony_config: Dict[str, Any],
                 available_actions: List[str]) -> Dict[str, Any]:
        is_pegasus = "pegasus" in personality.lower() or "pegasus" in str(pony_config.get("traits", [])).lower()
        is_unicorn = "unicorn" in personality.lower() or "unicorn" in str(pony_config.get("traits", [])).lower()
        is_earth = not is_pegasus and not is_unicorn

        # Определяем эмоцию по тексту
        emotion = self._detect_emotion(text) if text else random.choice(
            ["neutral", "happy", "happy", "neutral"])

        # Выбираем действие
        action_text = self._get_action_text(emotion, is_pegasus, is_unicorn, is_earth)
        action = self._select_action(emotion, text, available_actions)

        # Выбираем шаблон ответа
        other_ponies = ["Twilight Sparkle", "Rainbow Dash", "Pinkie Pie",
                        "Rarity", "Fluttershy", "Applejack"]
        other_pony = random.choice(other_ponies)

        if request_type == "spontaneous_speech":
            if random.random() < 0.3:
                template = random.choice(self.idle_thoughts)
            else:
                template = random.choice(self.reactions_to_user)
        elif request_type == "interaction":
            template = random.choice(self.interactions)
        elif text and self._is_greeting(text):
            template = random.choice(self.greetings)
        else:
            template = random.choice(self.reactions_to_user)

        response_text = template.format(
            action=action_text,
            user="friend",
            other_pony=other_pony,
        )

        # Подставляем catchphrase с шансом 20%
        catchphrases = pony_config.get("catchphrases", [])
        if catchphrases and random.random() < 0.2:
            response_text += f" {random.choice(catchphrases)}"

        return {
            "text": response_text,
            "emotion": emotion,
            "action": action,
            "action_duration": 3.0 if action else None,
            "target_pony": other_pony if request_type == "interaction" else None,
            "facial_expression": emotion,
        }

    def _detect_emotion(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["!", "yay", "woohoo", "awesome", "love", "great"]):
            return "happy"
        if any(w in text_lower for w in ["sad", "cry", "miss", "sorry", "goodbye"]):
            return "sad"
        if any(w in text_lower for w in ["angry", "grr", "mad", "buck", "stupid"]):
            return "angry"
        if any(w in text_lower for w in ["wow", "what", "oh", "whoa", "really"]):
            return "surprised"
        return random.choice(["neutral", "happy", "happy"])

    def _get_action_text(self, emotion: str, is_pegasus: bool,
                         is_unicorn: bool, is_earth: bool) -> str:
        actions = self.emotion_actions.get(emotion, ["*nods*"])
        action = random.choice(actions)

        # Заменяем на расоспецифичные действия
        if "wings" in action and not is_pegasus:
            action = "*trots*" if is_earth else "*uses magic*"
        if "magic" in action and not is_unicorn:
            action = "*stomps*" if is_earth else "*flutters wings*"

        return action

    def _select_action(self, emotion: str, text: str,
                       available_actions: List[str]) -> Optional[str]:
        if not text:
            return None

        text_lower = text.lower()
        action_map = {
            "buck": ["kick", "buck"],
            "rear": ["stand", "rise", "rear"],
            "sleep": ["sleep", "tired", "nap"],
            "conga": ["dance", "party"],
            "pose": ["pose", "look", "pretty"],
            "gallop": ["run", "fast", "race"],
            "walk": ["walk", "go", "move", "come"],
        }

        for action, keywords in action_map.items():
            if action in available_actions and any(k in text_lower for k in keywords):
                return action

        return None

    def _is_greeting(self, text: str) -> bool:
        text_lower = text.lower()
        greetings = ["hi", "hello", "hey", "howdy", "good morning",
                     "good afternoon", "good evening", "yo", "sup", "greetings"]
        return any(text_lower.startswith(g) for g in greetings)