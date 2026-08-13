# src_py/btcx.py
"""
Bad Token Contract system for Desktop Ponies RS
Token-based content moderation with contract types
"""

import sys
import json
from pathlib import Path
from typing import Dict, Optional, List
from enum import Enum


class ContractType(Enum):
    REPLACE = "REPLACE"
    CENSOR = "CENSOR"
    BLOCK = "BLOCK"
    WARN = "WARN"
    SILENT = "SILENT"


class BTCResult:
    def __init__(self, result_type: str, text: str = "", reason: str = ""):
        self.result_type = result_type
        self.text = text
        self.reason = reason

    def is_passed(self) -> bool:
        return self.result_type == "PASS"

    def is_blocked(self) -> bool:
        return self.result_type == "BLOCKED"

    def __repr__(self):
        return f"BTCResult({self.result_type}: {self.reason or self.text})"


class TokenContract:
    def __init__(self, contract: ContractType, severity: int, category: str,
                 replacement: Optional[str] = None):
        self.contract = contract
        self.severity = severity
        self.category = category
        self.replacement = replacement


class ContentConfig:
    MOON_KEY = "PRINCESS_LUNA_NIGHT_MODE_2024"

    def __init__(self):
        self._contracts: Dict[str, TokenContract] = {}
        self._whitelist: List[str] = []
        self._night_mode = False
        self._loaded = False

    def load_config(self, path: Path) -> int:
        if not path.exists():
            print(f"[BTC] File not found: {path}", file=sys.stderr)
            return 0

        text = self._read_utf32(path)
        if text is None:
            return 0

        try:
            config = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[BTC] Parse error: {e}", file=sys.stderr)
            return 0

        self._contracts.clear()
        self._whitelist.clear()
        count = 0

        token_contracts = config.get("token_contracts", {})
        if isinstance(token_contracts, dict):
            for category, group in token_contracts.items():
                if not isinstance(group, dict):
                    continue
                tokens = group.get("tokens", {})
                default_contract = group.get("contract", "REPLACE")

                if isinstance(tokens, dict):
                    for token, data in tokens.items():
                        if not isinstance(data, dict):
                            continue
                        contract_str = data.get("contract", default_contract)
                        replacement = data.get("replace")
                        severity = int(data.get("severity", 3))

                        contract_type = ContractType(contract_str)
                        self._contracts[token.lower()] = TokenContract(
                            contract=contract_type,
                            severity=severity,
                            category=category,
                            replacement=replacement,
                        )
                        count += 1

        exceptions = config.get("token_exceptions", {})
        if isinstance(exceptions, dict):
            whitelist = exceptions.get("whitelist", [])
            if isinstance(whitelist, list):
                self._whitelist = [str(w).lower() for w in whitelist]

        self._loaded = True
        print(f"[BTC] Loaded {count} contracts from {path.name}", file=sys.stderr)
        return count

    def apply_contracts(self, text: str) -> BTCResult:
        if not self._loaded or self._night_mode:
            return BTCResult("PASS", text)

        text_lower = text.lower()

        # Проверяем BLOCK-токены (приоритет)
        for word in text_lower.split():
            cleaned = ''.join(c for c in word if c.isalnum())
            if not cleaned or cleaned in self._whitelist:
                continue
            if cleaned in self._contracts:
                contract = self._contracts[cleaned]
                if contract.contract == ContractType.BLOCK:
                    return BTCResult(
                        "BLOCKED",
                        reason=f"BTC BLOCK: '{cleaned}' violates {contract.category} contract (severity {contract.severity})"
                    )

        # Применяем остальные контракты
        words = text.split()
        result = []
        changed = False
        warnings = []

        for word in words:
            cleaned = ''.join(c for c in word if c.isalnum()).lower()
            if not cleaned:
                result.append(word)
                continue
            if cleaned in self._whitelist:
                result.append(word)
                continue

            if cleaned in self._contracts:
                contract = self._contracts[cleaned]
                if contract.contract == ContractType.REPLACE:
                    result.append(contract.replacement or "***")
                    changed = True
                elif contract.contract == ContractType.CENSOR:
                    result.append("*" * len(cleaned))
                    changed = True
                elif contract.contract == ContractType.SILENT:
                    changed = True
                elif contract.contract == ContractType.WARN:
                    warnings.append(f"BTC WARN: '{cleaned}' ({contract.category})")
                    result.append(word)
                else:
                    result.append(word)
            else:
                result.append(word)

        if warnings:
            return BTCResult("WARNING", ' '.join(result), '; '.join(warnings))
        if changed:
            return BTCResult("MODIFIED", ' '.join(result))
        return BTCResult("PASS", text)

    def unlock_night(self, key: str) -> bool:
        if key == self.MOON_KEY:
            self._night_mode = True
            return True
        return False

    def lock_night(self):
        self._night_mode = False

    @property
    def is_night(self) -> bool:
        return self._night_mode

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def contract_count(self) -> int:
        return len(self._contracts)

    def _read_utf32(self, path: Path) -> Optional[str]:
        try:
            with open(path, 'rb') as f:
                raw = f.read()
            if len(raw) >= 4 and raw[:4] == b'\xff\xfe\x00\x00':
                text = raw[4:].decode('utf-32-le', errors='replace')
            elif len(raw) >= 4 and raw[:4] == b'\x00\x00\xfe\xff':
                text = raw[4:].decode('utf-32-be', errors='replace')
            else:
                try:
                    text = raw.decode('utf-32-le')
                except UnicodeDecodeError:
                    text = raw.decode('utf-8', errors='replace')
            if text and ord(text[0]) == 0xFEFF:
                text = text[1:]
            return text
        except Exception as e:
            print(f"[BTC] Read error: {e}", file=sys.stderr)
            return None