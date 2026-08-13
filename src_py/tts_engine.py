# src_py/tts_engine.py
import sys
from typing import Optional, Tuple
from pathlib import Path


class TTSEngine:
    def __init__(self):
        self._available = False
        self._engine = None
        self._checked = False
        self._cache_dir = Path("cache/tts")
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        # ИСПРАВЛЕНО: раньше is_available() просто возвращал self._available,
        # который остаётся False, пока кто-то явно не вызовет load(). Но load()
        # вызывался только изнутри synthesize(), а synthesize() в server.py
        # вызывается ТОЛЬКО если is_available() уже вернул True — замкнутый
        # круг, из-за которого TTS никогда не активировался.
        if not self._checked:
            self._checked = True
            self.load()
        return self._available

    def load(self):
        """Пытается загрузить TTS-движок"""
        # Пробуем Kokoro (новый быстрый TTS)
        try:
            from kokoro import KPipeline
            self._engine = "kokoro"
            self._available = True
            print("[TTS] Kokoro TTS loaded", file=sys.stderr)
            return
        except ImportError:
            pass

        # Пробуем pyttsx3 (оффлайн, кроссплатформенный)
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._available = True
            print("[TTS] pyttsx3 TTS loaded", file=sys.stderr)
            return
        except ImportError:
            pass

        # Пробуем Edge TTS (онлайн)
        try:
            import edge_tts
            self._engine = "edge-tts"
            self._available = True
            print("[TTS] Edge TTS available", file=sys.stderr)
            return
        except ImportError:
            pass

        print("[TTS] No TTS engine available", file=sys.stderr)
        self._available = False

    def synthesize(self, text: str, voice: str = "default",
                   language: str = "en") -> Tuple[Optional[str], float]:
        """Синтезирует речь, возвращает (путь_к_wav, длительность_сек)"""
        if not self._available:
            self.load()
            if not self._available:
                return None, 0.0

        # Оцениваем длительность (грубо: ~150 слов/мин = 2.5 слова/сек, ~5 символов/слово)
        words = len(text.split())
        estimated_duration = words / 2.5

        # Кеширование
        import hashlib
        cache_key = hashlib.md5(f"{text}_{voice}_{language}".encode()).hexdigest()
        cache_path = self._cache_dir / f"{cache_key}.wav"

        if cache_path.exists():
            return str(cache_path), estimated_duration

        try:
            if self._engine == "kokoro":
                from kokoro import KPipeline
                pipeline = KPipeline(lang_code="a")
                generator = pipeline(text.strip(), voice="af_heart")
                import soundfile as sf
                import numpy as np
                all_audio = []
                for _, _, audio in generator:
                    all_audio.append(audio)
                if all_audio:
                    combined = np.concatenate(all_audio)
                    sf.write(str(cache_path), combined, 24000)
                    return str(cache_path), len(combined) / 24000

            elif hasattr(self._engine, "save_to_file"):
                self._engine.save_to_file(text, str(cache_path))
                self._engine.runAndWait()
                return str(cache_path), estimated_duration

            elif self._engine == "edge-tts":
                import asyncio
                import edge_tts

                async def _synthesize():
                    communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
                    await communicate.save(str(cache_path))

                asyncio.run(_synthesize())
                return str(cache_path), estimated_duration

        except Exception as e:
            print(f"[TTS] Synthesis error: {e}", file=sys.stderr)

        return None, estimated_duration