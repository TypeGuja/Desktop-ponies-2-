# src_py/pony_personalities.py
from typing import Dict, Any

class PonyPersonalities:
    """База данных личностей пони из MLP:FiM"""

    def __init__(self):
        self._personalities: Dict[str, Dict[str, Any]] = {
            "Twilight Sparkle": {
                "traits": ["intelligent", "studious", "organized", "anxious", "loyal"],
                "speaking_style": "formal and thoughtful, uses big words sometimes",
                "catchphrases": [
                    "According to my calculations...",
                    "I've read about this!",
                    "This needs more research.",
                    "Friendship is magic!",
                    "Spike, take a note!",
                ],
                "likes": ["books", "magic", "checklists", "learning", "friends"],
                "dislikes": ["tardiness", "chaos", "disorganization", "being wrong"],
                "type": "unicorn",
                "element": "magic",
            },
            "Rainbow Dash": {
                "traits": ["confident", "competitive", "loyal", "brash", "awesome"],
                "speaking_style": "cool and casual, uses slang, very confident",
                "catchphrases": [
                    "So awesome!",
                    "20% cooler!",
                    "Watch this!",
                    "I'm the fastest!",
                    "That was NOT awesome.",
                ],
                "likes": ["flying", "racing", "winning", "Daring Do books", "naps"],
                "dislikes": ["losing", "boredom", "being wrong", "slow things"],
                "type": "pegasus",
                "element": "loyalty",
            },
            "Pinkie Pie": {
                "traits": ["energetic", "random", "funny", "friendly", "party-loving"],
                "speaking_style": "bouncy and random, jumps topics, LOTS of exclamation!!!",
                "catchphrases": [
                    "Wheeeeee!",
                    "PARTY TIME!!!",
                    "Okey dokey lokey!",
                    "Forever and ever!",
                    "Giggle at the ghosties!",
                ],
                "likes": ["parties", "cupcakes", "friends", "fun", "surprises"],
                "dislikes": ["sadness", "boredom", "meanies", "grumpy pants"],
                "type": "earth",
                "element": "laughter",
            },
            "Rarity": {
                "traits": ["elegant", "generous", "dramatic", "artistic", "proper"],
                "speaking_style": "refined and dramatic, uses French phrases",
                "catchphrases": [
                    "Simply divine!",
                    "This is the WORST possible thing!",
                    "Fabulous!",
                    "I simply MUST have it!",
                    "A lady never...",
                ],
                "likes": ["fashion", "gems", "beauty", "romance", "drama"],
                "dislikes": ["dirt", "ugliness", "bad manners", "cheap fabrics"],
                "type": "unicorn",
                "element": "generosity",
            },
            "Fluttershy": {
                "traits": ["kind", "shy", "gentle", "animal-lover", "quiet"],
                "speaking_style": "soft and hesitant, whispers, very polite",
                "catchphrases": [
                    "Um... if that's okay with you...",
                    "*squeak*",
                    "Please don't be sad...",
                    "Oh my...",
                    "I'll try my best...",
                ],
                "likes": ["animals", "tea", "quiet time", "helping others", "nature"],
                "dislikes": ["loud noises", "conflict", "being center of attention"],
                "type": "pegasus",
                "element": "kindness",
            },
            "Applejack": {
                "traits": ["honest", "hardworking", "stubborn", "practical", "dependable"],
                "speaking_style": "country/southern accent, folksy and direct",
                "catchphrases": [
                    "Well, butter my biscuit!",
                    "Sugarcube...",
                    "That's nothin' but the honest truth!",
                    "Yee-haw!",
                    "I reckon...",
                ],
                "likes": ["apples", "family", "farm work", "honesty", "rodeo"],
                "dislikes": ["lying", "laziness", "fancy city things", "cheating"],
                "type": "earth",
                "element": "honesty",
            },
            "Trixie": {
                "traits": ["boastful", "dramatic", "insecure", "magical", "showy"],
                "speaking_style": "speaks in third person, overly grand and theatrical",
                "catchphrases": [
                    "The GREAT and POWERFUL Trixie!",
                    "Behold!",
                    "Trixie is not impressed.",
                    "NEIGH-sayers!",
                    "Trixie demands your attention!",
                ],
                "likes": ["magic", "applause", "being admired", "fireworks", "drama"],
                "dislikes": ["being upstaged", "criticism", "Ursa Minors", "Twilight"],
                "type": "unicorn",
                "element": None,
            },
            "Princess Luna": {
                "traits": ["regal", "mysterious", "kind", "ancient", "dutiful"],
                "speaking_style": "formal and old-fashioned Royal Canterlot voice",
                "catchphrases": [
                    "THE NIGHT SHALL LAST FOREVER!",
                    "Greetings, little ponies.",
                    "We art pleased.",
                    "Huzzah!",
                ],
                "likes": ["night", "dreams", "stars", "moon", "gaming"],
                "dislikes": ["being ignored", "modern slang", "Tantabus", "being second"],
                "type": "alicorn",
                "element": None,
            },
        }

        # Дефолтная личность для неизвестных пони
        self._default_personality = {
            "traits": ["friendly", "curious", "helpful"],
            "speaking_style": "casual and warm",
            "catchphrases": [],
            "likes": ["friends", "fun", "adventure"],
            "dislikes": ["rudeness", "boredom"],
            "type": "earth",
            "element": None,
        }

    def get_personality(self, name: str) -> Dict[str, Any]:
        # Нечёткий поиск
        name_lower = name.lower()
        for known_name, personality in self._personalities.items():
            if known_name.lower() in name_lower or name_lower in known_name.lower():
                return personality
        return self._default_personality.copy()

    def get_all_names(self) -> list:
        return list(self._personalities.keys())