# src_py/stt_engine.py
import sys
from typing import Optional


class STTEngine:
    """Speech-to-Text (распознавание речи)"""

    def __init__(self):
        self._available = False
        self._recognizer = None
        self._checked = False

    def is_available(self) -> bool:
        # ИСПРАВЛЕНО: та же проблема, что в TTSEngine — is_available() никогда
        # не запускал load(), поэтому всегда возвращал False.
        if not self._checked:
            self._checked = True
            self.load()
        return self._available

    def load(self):
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._available = True
            print("[STT] SpeechRecognition loaded", file=sys.stderr)
        except ImportError:
            print("[STT] SpeechRecognition not available", file=sys.stderr)
            self._available = False

    def listen(self, timeout: float = 5.0) -> Optional[str]:
        """Слушает микрофон и возвращает распознанный текст"""
        if not self._available:
            self.load()
            if not self._available:
                return None

        import speech_recognition as sr

        try:
            with sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=5)

            text = self._recognizer.recognize_google(audio)
            return text
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except Exception as e:
            print(f"[STT] Error: {e}", file=sys.stderr)
            return None