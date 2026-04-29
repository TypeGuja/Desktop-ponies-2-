// src_rust/btcx.rs
// Bad Token Contract system for Desktop Ponies RS
use std::collections::HashMap;
use std::fs;
use std::path::Path;

#[derive(Clone, Debug)]
pub enum ContractType {
    Replace(String),     // Заменить на пони-версию
    Censor,              // Заменить на ***
    Block,               // Заблокировать сообщение целиком
    Warn,                // Пропустить, но записать в лог
    Silent,              // Удалить тихо
}

#[derive(Clone, Debug)]
pub struct TokenContract {
    pub contract: ContractType,
    pub severity: u8,
    pub category: String,
}

#[derive(Clone, Debug)]
pub struct ContentConfig {
    token_contracts: HashMap<String, TokenContract>,
    whitelist: Vec<String>,
    night_mode: bool,
    moon_key: String,
    loaded: bool,
    stats: ContractStats,
}

#[derive(Clone, Debug, Default)]
pub struct ContractStats {
    pub total_tokens: usize,
    pub replace_count: usize,
    pub censor_count: usize,
    pub block_count: usize,
    pub warn_count: usize,
    pub silent_count: usize,
}

#[derive(Debug, Clone)]
pub enum BTCResult {
    Pass(String),                // Текст прошёл без изменений
    Modified(String),            // Текст изменён (замены/цензура)
    Blocked(String),             // Сообщение заблокировано (причина)
    Warning(String, String),     // Предупреждение (токен, текст)
}

impl ContentConfig {
    const MOON_KEY: &'static str = "PRINCESS_LUNA_NIGHT_MODE_2024";

    pub fn new() -> Self {
        Self {
            token_contracts: HashMap::new(),
            whitelist: Vec::new(),
            night_mode: false,
            moon_key: Self::MOON_KEY.to_string(),
            loaded: false,
            stats: ContractStats::default(),
        }
    }

    /// Загружает BTC-конфигурацию из файла
    pub fn load_config<P: AsRef<Path>>(&mut self, path: P) -> Result<usize, String> {
        let path = path.as_ref();
        let bytes = fs::read(path).map_err(|e| format!("Cannot read BTC: {}", e))?;
        let text = Self::decode_utf32(&bytes)?;
        let config: serde_json::Value = serde_json::from_str(&text)
            .map_err(|e| format!("BTC parse error: {}", e))?;

        self.token_contracts.clear();
        self.whitelist.clear();

        let mut count = 0;

        // Загружаем контракты токенов
        if let Some(contracts) = config.get("token_contracts").and_then(|v| v.as_object()) {
            for (category, contract_group) in contracts {
                if let Some(tokens) = contract_group.get("tokens").and_then(|v| v.as_object()) {
                    let default_contract = contract_group.get("contract")
                        .and_then(|v| v.as_str())
                        .unwrap_or("REPLACE");

                    for (token, token_data) in tokens {
                        let contract_type = token_data.get("contract")
                            .and_then(|v| v.as_str())
                            .unwrap_or(default_contract);

                        let replacement = token_data.get("replace")
                            .and_then(|v| v.as_str());

                        let severity = token_data.get("severity")
                            .and_then(|v| v.as_u64())
                            .unwrap_or(3) as u8;

                        let contract = match contract_type {
                            "BLOCK" => ContractType::Block,
                            "CENSOR" => ContractType::Censor,
                            "WARN" => ContractType::Warn,
                            "SILENT" => ContractType::Silent,
                            _ => ContractType::Replace(
                                replacement.unwrap_or("***").to_string()
                            ),
                        };

                        match &contract {
                            ContractType::Replace(_) => self.stats.replace_count += 1,
                            ContractType::Censor => self.stats.censor_count += 1,
                            ContractType::Block => self.stats.block_count += 1,
                            ContractType::Warn => self.stats.warn_count += 1,
                            ContractType::Silent => self.stats.silent_count += 1,
                        }

                        self.token_contracts.insert(
                            token.to_lowercase(),
                            TokenContract {
                                contract,
                                severity,
                                category: category.to_string(),
                            },
                        );
                        count += 1;
                    }
                }
            }
        }

        // Загружаем исключения
        if let Some(exceptions) = config.get("token_exceptions")
            .and_then(|v| v.get("whitelist"))
            .and_then(|v| v.as_array())
        {
            for item in exceptions {
                if let Some(s) = item.as_str() {
                    self.whitelist.push(s.to_lowercase());
                }
            }
        }

        self.stats.total_tokens = count;
        self.loaded = true;
        Ok(count)
    }

    /// Применяет BTC-контракты к тексту
    pub fn apply_contracts(&self, text: &str) -> BTCResult {
        if !self.loaded || self.night_mode {
            return BTCResult::Pass(text.to_string());
        }

        let text_lower = text.to_lowercase();
        let mut modified = text.to_string();
        let mut blocked = false;
        let mut block_reason = String::new();
        let mut warnings = Vec::new();

        // Сначала проверяем BLOCK-токены (приоритет)
        for word in text_lower.split_whitespace() {
            let cleaned: String = word.chars()
                .filter(|c| c.is_alphanumeric())
                .collect();
            if cleaned.is_empty() { continue; }

            if self.whitelist.contains(&cleaned) {
                continue;
            }

            if let Some(contract) = self.token_contracts.get(&cleaned) {
                match &contract.contract {
                    ContractType::Block => {
                        blocked = true;
                        block_reason = format!(
                            "BTC BLOCK: token '{}' violates {} contract (severity {})",
                            cleaned, contract.category, contract.severity
                        );
                        break;
                    }
                    _ => {}
                }
            }
        }

        if blocked {
            return BTCResult::Blocked(block_reason);
        }

        // Применяем остальные контракты
        let words: Vec<String> = modified.split_whitespace()
            .map(|s| s.to_string()).collect();
        let mut result_words = Vec::new();
        let mut changed = false;

        for word in &words {
            let cleaned: String = word.chars()
                .filter(|c| c.is_alphanumeric())
                .collect::<String>()
                .to_lowercase();

            if cleaned.is_empty() {
                result_words.push(word.clone());
                continue;
            }

            if self.whitelist.contains(&cleaned) {
                result_words.push(word.clone());
                continue;
            }

            if let Some(contract) = self.token_contracts.get(&cleaned) {
                match &contract.contract {
                    ContractType::Replace(replacement) => {
                        result_words.push(replacement.clone());
                        changed = true;
                    }
                    ContractType::Censor => {
                        result_words.push("*".repeat(cleaned.len()));
                        changed = true;
                    }
                    ContractType::Silent => {
                        // Не добавляем слово
                        changed = true;
                    }
                    ContractType::Warn => {
                        warnings.push(format!(
                            "BTC WARN: token '{}' ({}) used",
                            cleaned, contract.category
                        ));
                        result_words.push(word.clone());
                    }
                    ContractType::Block => {
                        // Уже обработано выше
                        result_words.push(word.clone());
                    }
                }
            } else {
                result_words.push(word.clone());
            }
        }

        if !warnings.is_empty() {
            return BTCResult::Warning(
                warnings.join("; "),
                result_words.join(" ")
            );
        }

        if changed {
            BTCResult::Modified(result_words.join(" "))
        } else {
            BTCResult::Pass(text.to_string())
        }
    }

    /// Разблокировка ночного режима (все контракты отключаются)
    pub fn unlock_night(&mut self, key: &str) -> bool {
        if key == self.moon_key {
            self.night_mode = true;
            true
        } else {
            false
        }
    }

    pub fn lock_night(&mut self) {
        self.night_mode = false;
    }

    pub fn is_night(&self) -> bool { self.night_mode }
    pub fn is_loaded(&self) -> bool { self.loaded }
    pub fn contract_stats(&self) -> &ContractStats { &self.stats }

    fn decode_utf32(bytes: &[u8]) -> Result<String, String> {
        if bytes.len() < 4 {
            return Ok(String::from_utf8_lossy(bytes).to_string());
        }
        let (data, is_le) = match &bytes[0..4] {
            [0xFF, 0xFE, 0x00, 0x00] => (&bytes[4..], true),
            [0x00, 0x00, 0xFE, 0xFF] => (&bytes[4..], false),
            _ => (bytes, true),
        };
        let mut chars = Vec::new();
        for chunk in data.chunks_exact(4) {
            if chunk.len() < 4 { break; }
            let code = if is_le {
                u32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]])
            } else {
                u32::from_be_bytes([chunk[0], chunk[1], chunk[2], chunk[3]])
            };
            if let Some(c) = char::from_u32(code) {
                chars.push(c);
            }
        }
        let text: String = chars.into_iter().collect();
        Ok(text.trim_start_matches('\u{FEFF}').to_string())
    }
}