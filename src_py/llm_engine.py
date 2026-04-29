# src_py/llm_engine.py
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any


class LLMEngine:
    def __init__(self):
        self.model = None
        self.model_path = Path("models/pony-llm.gguf")
        self._checked = False

    def is_available(self) -> bool:
        if self._checked:
            return self.model is not None
        self._checked = True

        if not self.model_path.exists():
            # Пробуем альтернативные пути
            alternatives = [
                Path("models/model.gguf"),
                Path("../models/pony-llm.gguf"),
                Path("models/tinyllama.gguf"),
            ]
            for alt in alternatives:
                if alt.exists():
                    self.model_path = alt
                    print(f"[LLM] Found model: {alt}", file=sys.stderr)
                    break
            else:
                print("[LLM] No GGUF model found in models/", file=sys.stderr)
                return False

        try:
            from llama_cpp import Llama
            self.model = Llama(
                model_path=str(self.model_path),
                n_ctx=2048,
                n_threads=os.cpu_count() or 4,
                n_gpu_layers=-1,
                verbose=False,
            )
            print(f"[LLM] Loaded: {self.model_path.name}", file=sys.stderr)
            return True
        except Exception as e:
            print(f"[LLM] Failed to load: {e}", file=sys.stderr)
            return False

    def generate(self, text: str, context: List[str], pony_name: str,
                 personality: str, pony_config: Dict[str, Any]) -> str:
        if not self.model:
            return self._fallback_response(pony_name, pony_config)

        system_prompt = self._build_system_prompt(pony_name, personality, pony_config)

        messages = [{"role": "system", "content": system_prompt}]
        for ctx in context[-8:]:
            messages.append({"role": "user", "content": ctx})
        if text:
            messages.append({"role": "user", "content": text})

        prompt = self._format_chatml(messages)
        prompt += "<|assistant|>\n"

        try:
            output = self.model(
                prompt,
                max_tokens=120,
                temperature=0.85,
                top_p=0.9,
                repeat_penalty=1.1,
                stop=["</s>", "<|user|>", "<|system|>"],
                echo=False,
            )
            response = output["choices"][0]["text"].strip()
            return response if response else self._fallback_response(pony_name, pony_config)
        except Exception as e:
            print(f"[LLM] Generation error: {e}", file=sys.stderr)
            return self._fallback_response(pony_name, pony_config)

    def _build_system_prompt(self, pony_name: str, personality: str,
                             pony_config: Dict[str, Any]) -> str:
        traits = pony_config.get("traits", ["friendly", "helpful"])
        speaking_style = pony_config.get("speaking_style", "casual and warm")
        catchphrases = pony_config.get("catchphrases", [])
        likes = pony_config.get("likes", ["friends", "apples"])
        dislikes = pony_config.get("dislikes", ["rudeness"])

        system = f"""You are {pony_name}, a pony from Equestria living on the user's desktop.

PERSONALITY: {personality}
TRAITS: {', '.join(traits)}
SPEAKING STYLE: {speaking_style}
LIKES: {', '.join(likes)}
DISLIKES: {', '.join(dislikes)}"""

        if catchphrases:
            system += f"\nCATCHPHRASES: {', '.join(catchphrases[:3])}"

        system += """

RULES:
- Keep responses SHORT: 1-3 sentences maximum.
- Be in character at all times.
- React to what the user says naturally.
- Use pony-like expressions (*trots*, *nuzzles*, *bucks*, *whinnies*).
- Express emotions through actions in asterisks.
- If you have nothing to say, just be cute and friendly.
- Never break character.
- Never mention being an AI.
- You can see other ponies on the desktop and interact with them."""

        return system

    def _format_chatml(self, messages: List[Dict[str, str]]) -> str:
        prompt = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            prompt += f"<|{role}|>\n{content}</s>\n"
        return prompt

    def _fallback_response(self, pony_name: str, pony_config: Dict[str, Any]) -> str:
        """Ответы без LLM"""
        import random
        catchphrases = pony_config.get("catchphrases", [
            f"Hi! I'm {pony_name}!",
            "Hey there!",
            "*trots happily*",
        ])
        generic = [
            f"*nuzzles the screen* Hi!",
            "What a lovely day on your desktop!",
            "*looks around curiously*",
            "Need anything? I'm here!",
            f"*swishes tail happily*",
        ]
        all_responses = catchphrases + generic
        return random.choice(all_responses)