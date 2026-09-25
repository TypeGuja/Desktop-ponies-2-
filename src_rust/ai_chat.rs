// src_rust/ai_chat.rs
//
// Диалоги пони через облачную нейросеть (любой OpenAI-совместимый
// /chat/completions). Правило проекта: нет доступной нейросети — нет и
// диалогов. Никаких шаблонных «заготовленных» реплик здесь нет: если ключ не
// задан (`AiConfig::is_available() == false`), интерфейс просто не показывает
// пункт «Talk» и не запускает спонтанные реплики.
//
// Ключ хранится в отдельном ai_config.json рядом с exe (он в .gitignore), а не
// в desktop_ponies_settings.json, который лежит в репозитории. Переменные
// окружения PONY_AI_KEY / PONY_AI_BASE_URL / PONY_AI_MODEL имеют приоритет.

use serde::{Deserialize, Serialize};
use std::path::Path;
use std::time::Duration;

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct AiConfig {
    pub base_url: String,
    pub api_key: String,
    pub model: String,
    /// Язык ответов по умолчанию (если пользователь пишет на другом — модель
    /// отвечает на его языке).
    pub language: String,
    /// Пони сами изредка комментируют происходящее (только если ИИ доступен).
    pub spontaneous: bool,
}

impl Default for AiConfig {
    fn default() -> Self {
        Self {
            base_url: "https://api.openai.com/v1".to_string(),
            api_key: String::new(),
            model: "gpt-4o-mini".to_string(),
            language: "Russian".to_string(),
            spontaneous: true,
        }
    }
}

impl AiConfig {
    pub fn load(path: &Path) -> Self {
        let mut cfg: AiConfig = std::fs::read_to_string(path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default();

        if let Ok(v) = std::env::var("PONY_AI_KEY") { if !v.trim().is_empty() { cfg.api_key = v; } }
        if let Ok(v) = std::env::var("PONY_AI_BASE_URL") { if !v.trim().is_empty() { cfg.base_url = v; } }
        if let Ok(v) = std::env::var("PONY_AI_MODEL") { if !v.trim().is_empty() { cfg.model = v; } }
        cfg
    }

    pub fn save(&self, path: &Path) {
        match serde_json::to_string_pretty(self) {
            Ok(json) => {
                if let Err(e) = std::fs::write(path, json) {
                    eprintln!("[AI] Failed to save config: {}", e);
                }
            }
            Err(e) => eprintln!("[AI] Config serialization error: {}", e),
        }
    }

    /// Нейросеть «есть», только если заданы ключ, адрес и модель.
    pub fn is_available(&self) -> bool {
        !self.api_key.trim().is_empty()
            && !self.base_url.trim().is_empty()
            && !self.model.trim().is_empty()
    }
}

#[derive(Clone, Debug)]
pub struct ChatMessage {
    pub role: &'static str, // "user" | "assistant"
    pub content: String,
}

/// Максимум сообщений истории, которые отправляются в модель.
pub const MAX_HISTORY: usize = 12;

pub fn build_system_prompt(cfg: &AiConfig, pony_name: &str, categories: &[String], others: &[String]) -> String {
    let mut s = format!(
        "You are {name}, a pony from My Little Pony: Friendship is Magic, living on the user's desktop as a small desktop pet.\n\
         Stay in character at all times and never mention being an AI or a language model.\n\
         Reply in {lang} unless the user writes in another language - then reply in theirs.\n\
         Keep every reply to 1-2 short sentences (under 200 characters). Plain text only: no markdown, no emoji, no *actions in asterisks*.",
        name = pony_name,
        lang = cfg.language,
    );
    if !categories.is_empty() {
        s.push_str(&format!("\nYour categories: {}.", categories.join(", ")));
    }
    if !others.is_empty() {
        s.push_str(&format!("\nOther ponies currently on the desktop: {}.", others.join(", ")));
    }
    s
}

/// Запрашивает ответ в отдельном потоке (UI не блокируется) и вызывает
/// `on_done` из этого потока — вызывающий код должен переслать результат в
/// цикл событий (через EventLoopProxy).
pub fn request_async<F>(cfg: AiConfig, system: String, history: Vec<ChatMessage>, on_done: F)
where
    F: FnOnce(Result<String, String>) + Send + 'static,
{
    std::thread::spawn(move || {
        on_done(request_blocking(&cfg, &system, &history));
    });
}

fn request_blocking(cfg: &AiConfig, system: &str, history: &[ChatMessage]) -> Result<String, String> {
    let url = format!("{}/chat/completions", cfg.base_url.trim().trim_end_matches('/'));

    let mut messages = vec![serde_json::json!({ "role": "system", "content": system })];
    for m in history {
        messages.push(serde_json::json!({ "role": m.role, "content": m.content }));
    }
    let body = serde_json::json!({
        "model": cfg.model,
        "messages": messages,
        "max_tokens": 150,
        "temperature": 0.9,
    });

    let agent = ureq::AgentBuilder::new()
        .timeout(Duration::from_secs(30))
        .build();

    let resp = agent
        .post(&url)
        .set("Authorization", &format!("Bearer {}", cfg.api_key.trim()))
        .send_json(body);

    match resp {
        Ok(r) => {
            let v: serde_json::Value = r.into_json().map_err(|e| format!("bad response: {}", e))?;
            v["choices"][0]["message"]["content"]
                .as_str()
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .ok_or_else(|| "empty response".to_string())
        }
        Err(ureq::Error::Status(code, r)) => {
            let text = r.into_string().unwrap_or_default();
            let short: String = text.chars().take(200).collect();
            Err(format!("HTTP {}: {}", code, short))
        }
        Err(e) => Err(e.to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpListener;

    fn mock_server(status: &str, body: &str) -> (String, std::thread::JoinHandle<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let url = format!("http://{}/v1", listener.local_addr().unwrap());
        let (status, body) = (status.to_string(), body.to_string());
        let h = std::thread::spawn(move || {
            let (mut s, _) = listener.accept().unwrap();
            // Читаем запрос целиком: заголовки, затем Content-Length байт тела.
            let mut data: Vec<u8> = Vec::new();
            let mut chunk = [0u8; 4096];
            loop {
                let n = s.read(&mut chunk).unwrap();
                if n == 0 {
                    break;
                }
                data.extend_from_slice(&chunk[..n]);
                if let Some(pos) = data.windows(4).position(|w| w == b"\r\n\r\n") {
                    let head = String::from_utf8_lossy(&data[..pos]).to_lowercase();
                    let len = head
                        .lines()
                        .find_map(|l| l.strip_prefix("content-length:").and_then(|v| v.trim().parse::<usize>().ok()))
                        .unwrap_or(0);
                    if data.len() >= pos + 4 + len {
                        break;
                    }
                }
            }
            let req = String::from_utf8_lossy(&data).to_string();
            let resp = format!(
                "HTTP/1.1 {}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                status, body.len(), body
            );
            s.write_all(resp.as_bytes()).unwrap();
            req
        });
        (url, h)
    }

    fn cfg(url: String) -> AiConfig {
        AiConfig { base_url: url, api_key: "k123".into(), model: "m".into(), language: "Russian".into(), spontaneous: true }
    }

    #[test]
    fn parses_reply_and_sends_auth() {
        let (url, h) = mock_server("200 OK", r#"{"choices":[{"message":{"content":"  Привет!  "}}]}"#);
        let hist = vec![ChatMessage { role: "user", content: "hi".into() }];
        let r = request_blocking(&cfg(url), "sys", &hist);
        assert_eq!(r.unwrap(), "Привет!");
        let req = h.join().unwrap();
        assert!(req.contains("POST /v1/chat/completions"));
        assert!(req.to_lowercase().contains("authorization: bearer k123"));
    }

    #[test]
    fn reports_http_error() {
        let (url, _h) = mock_server("401 Unauthorized", r#"{"error":"bad key"}"#);
        let r = request_blocking(&cfg(url), "sys", &[]);
        assert!(r.unwrap_err().starts_with("HTTP 401"));
    }

    #[test]
    fn unavailable_without_key() {
        assert!(!AiConfig::default().is_available());
    }
}
