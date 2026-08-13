#!/usr/bin/env python3
# ai_server.py — Python AI сервер для Desktop Ponies RS
import sys
import json
import random
import traceback

# Хранилище сессий пони
pony_sessions = {}

# Стандартные ответы, если нейросеть недоступна
FALLBACK_SPEECHES = {
    "Twilight Sparkle": [
        "According to my calculations, friendship is optimal!",
        "I've been studying the magic of friendship all day.",
        "Spike, have you seen my quill?",
        "There's always something new to learn!",
    ],
    "Applejack": [
        "Howdy, partner!",
        "I better get buckin' soon.",
        "Soup's on, everypony!",
        "Honesty is the best policy, sugarcube.",
    ],
    "Rainbow Dash": [
        "I'm the fastest flyer in Equestria!",
        "Twenty percent cooler!",
        "Let's do this!",
        "That was awesome!",
    ],
    "Pinkie Pie": [
        "Wheeeee!",
        "Let's throw a party!",
        "I know just the thing — cupcakes!",
        "Are you thinking what I'm thinking?",
    ],
    "Rarity": [
        "Darling, that is simply divine!",
        "I simply must accessorize!",
        "A lady never reveals her secrets.",
        "This is the worst possible thing!",
    ],
    "Fluttershy": [
        "Um, if that's okay with you...",
        "I'd like to be a tree.",
        "You're going to LOVE it!",
        "*squeak*",
    ],
}

FALLBACK_EMOTIONS = [
    "neutral", "happy", "excited", "surprised",
    "amused", "thoughtful", "silly",
]

FALLBACK_ACTIONS = [
    "idle", "walk", "pose", "rear", "buck",
    "conga", "sleep",
]


def get_fallback_response(pony_name, request_type):
    """Генерирует ответ без нейросети"""
    speeches = FALLBACK_SPEECHES.get(pony_name, [
        "Hello everypony!",
        "Friendship is magic!",
        "Let's go on an adventure!",
    ])

    text = random.choice(speeches)
    emotion = random.choice(FALLBACK_EMOTIONS)

    if request_type == "interaction":
        action = random.choice(["pose", "walk", "conga", "rear"])
    else:
        action = random.choice(["idle", "pose", "walk"])

    return {
        "text": text,
        "emotion": emotion,
        "action": action,
    }


def try_ai_response(request):
    """
    Попытаться использовать настоящую нейросеть.
    Замени этот код на вызов OpenAI API, локальной LLM, или что угодно.
    """
    try:
        # === ПРИМЕР: OpenAI API ===
        # import openai
        # openai.api_key = "sk-..."
        # response = openai.ChatCompletion.create(
        #     model="gpt-3.5-turbo",
        #     messages=[
        #         {"role": "system", "content": f"You are {request['pony_name']} from My Little Pony. Keep responses short and in character."},
        #         {"role": "user", "content": "Say something spontaneous!"},
        #     ],
        #     max_tokens=50,
        # )
        # return {
        #     "text": response.choices[0].message.content.strip(),
        #     "emotion": "neutral",
        #     "action": "idle",
        # }

        # === ПРИМЕР: Локальная LLM через Ollama ===
        # import requests
        # prompt = f"You are {request['pony_name']} from My Little Pony. Say something short and in character."
        # r = requests.post('http://localhost:11434/api/generate', json={
        #     "model": "llama2",
        #     "prompt": prompt,
        #     "stream": False,
        # })
        # return {
        #     "text": r.json()['response'].strip(),
        #     "emotion": "neutral",
        #     "action": "idle",
        # }

        # Пока возвращаем None — используем fallback
        return None

    except Exception:
        return None


def handle_request(request):
    """Обрабатывает один запрос от Rust"""
    request_id = request.get("request_id", 0)
    request_type = request.get("request_type", "speech")
    pony_name = request.get("pony_name", "Unknown Pony")
    # ИСПРАВЛЕНО: personality/text/context/language раньше читались из
    # запроса, но нигде не использовались (pyflakes: assigned but never used).
    # try_ai_response() получает весь request целиком, так что здесь эти поля
    # не нужны.

    # Пробуем AI
    ai_response = try_ai_response(request)
    if ai_response:
        return {
            "request_id": request_id,
            "text": ai_response["text"],
            "emotion": ai_response.get("emotion"),
            "action": ai_response.get("action"),
        }

    # Fallback
    fallback = get_fallback_response(pony_name, request_type)
    return {
        "request_id": request_id,
        "text": fallback["text"],
        "emotion": fallback.get("emotion"),
        "action": fallback.get("action"),
    }


def main():
    """Главный цикл: читаем JSON-строки из stdin, пишем ответы в stdout"""
    # Отправляем ready после получения handshake
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_type = request.get("type", "")

        if req_type == "handshake":
            print(json.dumps({"status": "ready", "request_id": 0}))
            sys.stdout.flush()
            continue

        if req_type == "shutdown":
            break

        response = handle_request(request)
        print(json.dumps(response))
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(file=sys.stderr)