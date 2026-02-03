# toon.py
"""
Бинарный протокол «Toon» – лёгковесный заменитель JSON.

Если установлен `msgpack` (pip install msgpack‑python) – используется
MessagePack, иначе – встроенный `pickle`.  Оба варианта работают с
обычными Python‑словарями, поэтому код‑база сервера и клиента
не меняется, кроме импорта:  ``import toon``  и вызовы
``toon.encode(dict)`` / ``toon.decode(bytes)``.
"""

from typing import Any, Dict

# --------------------------------------------------------------
#   Выбор реализации (MessagePack > pickle)
# --------------------------------------------------------------
try:
    import msgpack                      # быстрый и компактный
    _USE_MSGPACK = True
except Exception:                       # отсутствие msgpack – fallback
    import pickle
    _USE_MSGPACK = False


def encode(message: Dict[str, Any]) -> bytes:
    """Сериализовать словарь в бинарный поток."""
    if _USE_MSGPACK:
        # use_bin_type=True → гарантируем, что строки → UTF‑8, а не bytes
        return msgpack.packb(message, use_bin_type=True)
    return pickle.dumps(message, protocol=pickle.HIGHEST_PROTOCOL)


def decode(data: bytes) -> Dict[str, Any]:
    """Десериализовать бинарный поток обратно в словарь."""
    if _USE_MSGPACK:
        # raw=False → получаем строки, а не байтовые объекты
        return msgpack.unpackb(data, raw=False)
    return pickle.loads(data)
