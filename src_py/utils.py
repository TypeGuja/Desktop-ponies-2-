# src_py/utils.py
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Безопасная загрузка JSON"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[UTIL] Failed to load {path}: {e}", file=sys.stderr)
        return None


def save_json(path: Path, data: Dict[str, Any]) -> bool:
    """Безопасное сохранение JSON"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[UTIL] Failed to save {path}: {e}", file=sys.stderr)
        return False


def ensure_dir(path: Path) -> Path:
    """Создаёт директорию если не существует"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def log(message: str, level: str = "INFO"):
    """Логирование в stderr (чтобы не мешать IPC через stdout)"""
    print(f"[{level}] {message}", file=sys.stderr, flush=True)