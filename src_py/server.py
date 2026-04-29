# src_py/server.py
import sys
import json
import traceback
from typing import Optional, Dict, Any

from llm_engine import LLMEngine
from emotion_engine import EmotionEngine
from tts_engine import TTSEngine
from stt_engine import STTEngine
from pony_personalities import PonyPersonalities
from rule_engine import RuleEngine


class IPCServer:
    """Сервер, общающийся через stdin/stdout JSON-строками с Rust"""

    def __init__(self):
        self.llm = LLMEngine()
        self.emotion = EmotionEngine()
        self.tts = TTSEngine()
        self.stt = STTEngine()
        self.personalities = PonyPersonalities()
        self.rule_engine = RuleEngine()
        self.running = True

    def run(self):
        print("[PY] IPC Server ready", file=sys.stderr, flush=True)

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = self.handle_request(request)
                response_json = json.dumps(response, ensure_ascii=False)
                print(response_json, flush=True)
            except json.JSONDecodeError as e:
                error_response = {
                    "request_id": 0,
                    "response_type": "error",
                    "text": "",
                    "emotion": None,
                    "action": None,
                    "action_duration": None,
                    "target_pony": None,
                    "tts_audio_path": None,
                    "tts_duration": None,
                    "facial_expression": None,
                    "error": f"Invalid JSON: {e}",
                }
                print(json.dumps(error_response), flush=True)
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                error_response = {
                    "request_id": 0,
                    "response_type": "error",
                    "text": "",
                    "emotion": None,
                    "action": None,
                    "action_duration": None,
                    "target_pony": None,
                    "tts_audio_path": None,
                    "tts_duration": None,
                    "facial_expression": None,
                    "error": str(e),
                }
                print(json.dumps(error_response), flush=True)

            if not self.running:
                break

    def handle_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        request_type = req.get("request_type", "")
        request_id = req.get("request_id", 0)
        text = req.get("text", "")
        pony_name = req.get("pony_name", "Anonymous Pony")
        pony_personality = req.get("pony_personality", None)
        context = req.get("context", [])
        available_actions = req.get("available_actions", [])
        language = req.get("language", "en")

        base_response = {
            "request_id": request_id,
            "response_type": "text",
            "text": "",
            "emotion": None,
            "action": None,
            "action_duration": None,
            "target_pony": None,
            "tts_audio_path": None,
            "tts_duration": None,
            "facial_expression": None,
            "error": None,
        }

        if request_type == "shutdown":
            self.running = False
            base_response["text"] = "Goodbye!"
            base_response["emotion"] = "happy"
            return base_response

        # Получаем личность пони
        personality = pony_personality or pony_name
        pony_config = self.personalities.get_personality(personality)

        # Пробуем LLM, если доступен
        if self.llm.is_available():
            return self._handle_with_llm(
                request_type, text, pony_name, personality,
                pony_config, context, available_actions,
                language, base_response, request_id,
            )
        else:
            # Fallback: rule-based engine
            return self._handle_with_rules(
                request_type, text, pony_name, personality,
                pony_config, available_actions,
                base_response, request_id,
            )

    def _handle_with_llm(self, request_type, text, pony_name, personality,
                         pony_config, context, available_actions,
                         language, base_response, request_id):
        """Обработка через LLM"""
        response_text = self.llm.generate(
            text=text,
            context=context,
            pony_name=pony_name,
            personality=personality,
            pony_config=pony_config,
        )

        emotion = self.emotion.classify(response_text)
        action = self.emotion.suggest_action(
            emotion, available_actions, response_text
        )

        base_response["text"] = response_text
        base_response["emotion"] = emotion
        base_response["action"] = action
        base_response["action_duration"] = 3.0 if action else None

        # TTS (если включено)
        if self.tts.is_available():
            audio_path, duration = self.tts.synthesize(
                response_text, voice=pony_name, language=language
            )
            base_response["tts_audio_path"] = audio_path
            base_response["tts_duration"] = duration

        return base_response

    def _handle_with_rules(self, request_type, text, pony_name, personality,
                           pony_config, available_actions, base_response, request_id):
        """Обработка через rule-based engine"""
        result = self.rule_engine.generate(
            request_type=request_type,
            text=text,
            pony_name=pony_name,
            personality=personality,
            pony_config=pony_config,
            available_actions=available_actions,
        )

        base_response["text"] = result["text"]
        base_response["emotion"] = result.get("emotion", "neutral")
        base_response["action"] = result.get("action")
        base_response["action_duration"] = result.get("action_duration")
        base_response["target_pony"] = result.get("target_pony")
        base_response["facial_expression"] = result.get("facial_expression")

        return base_response


class HTTPServer:
    """HTTP-сервер для отладки и внешних клиентов"""

    def __init__(self, port: int = 8765):
        self.port = port
        self.ipc_server = IPCServer()

    def run(self):
        try:
            from http.server import HTTPServer as HTTPd, BaseHTTPRequestHandler
            import json as json_module

            ipc = self.ipc_server

            class Handler(BaseHTTPRequestHandler):
                def do_POST(self):
                    content_length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_length)
                    request = json_module.loads(body)
                    response = ipc.handle_request(request)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json_module.dumps(response, ensure_ascii=False).encode())

                def do_GET(self):
                    if self.path == "/health":
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(b'{"status": "ok"}')
                    else:
                        self.send_response(404)
                        self.end_headers()

                def log_message(self, format, *args):
                    print(f"[HTTP] {format % args}", file=sys.stderr)

            server = HTTPd(('localhost', self.port), Handler)
            print(f"[PY] HTTP server listening on localhost:{self.port}", file=sys.stderr)
            server.serve_forever()
        except ImportError:
            print("[PY] HTTP server not available (no http.server module)", file=sys.stderr)