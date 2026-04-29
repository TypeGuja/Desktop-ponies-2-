// src_rust/python_bridge.rs
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;

#[derive(Clone, Debug)]
pub struct AIRequest {
    pub request_id: u64,
    pub request_type: String,
    pub text: String,
    pub pony_name: String,
    pub pony_personality: Option<String>,
    pub context: Vec<String>,
    pub available_actions: Vec<String>,
    pub language: String,
}

#[derive(Clone, Debug)]
pub struct AIResponse {
    pub request_id: u64,
    pub text: String,
    pub emotion: Option<String>,
    pub action: Option<String>,
}

pub struct PythonBridge {
    process: Option<Child>,
    stdin: Option<Mutex<ChildStdin>>,
    stdout: Option<Mutex<BufReader<ChildStdout>>>,
    request_counter: u64,
    running: bool,
}

impl PythonBridge {
    pub fn new() -> Self {
        Self {
            process: None,
            stdin: None,
            stdout: None,
            request_counter: 0,
            running: false,
        }
    }

    pub fn start(&mut self, python_path: &str, script_path: &str) -> Result<(), String> {
        if self.running {
            return Ok(());
        }

        let mut child = Command::new(python_path)
            .arg(script_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("Failed to start Python AI: {}", e))?;

        let stdin = child
            .stdin
            .take()
            .ok_or("Failed to capture Python stdin")?;
        let stdout = child
            .stdout
            .take()
            .ok_or("Failed to capture Python stdout")?;

        self.stdin = Some(Mutex::new(stdin));
        self.stdout = Some(Mutex::new(BufReader::new(stdout)));
        self.process = Some(child);
        self.running = true;

        // Отправляем рукопожатие
        self.send_raw(r#"{"type":"handshake","version":"1.0"}"#)?;

        // Читаем ответ
        let response = self.read_response()?;
        if !response.contains("ready") {
            return Err(format!("Python AI handshake failed: {}", response));
        }

        println!("[PythonBridge] AI process started and ready");
        Ok(())
    }

    pub fn send_request(&mut self, mut request: AIRequest) -> Result<AIResponse, String> {
        if !self.running {
            return Err("Python bridge not running".to_string());
        }

        self.request_counter += 1;
        request.request_id = self.request_counter;

        let json = serde_json::to_string(&RequestWire {
            request_id: request.request_id,
            request_type: request.request_type.clone(),
            text: request.text.clone(),
            pony_name: request.pony_name.clone(),
            pony_personality: request.pony_personality.clone(),
            context: request.context.clone(),
            available_actions: request.available_actions.clone(),
            language: request.language.clone(),
        })
            .map_err(|e| format!("Serialization error: {}", e))?;

        self.send_raw(&json)?;
        let response_text = self.read_response()?;

        let wire: ResponseWire = serde_json::from_str(&response_text)
            .map_err(|e| format!("Parse error for '{}': {}", response_text, e))?;

        Ok(AIResponse {
            request_id: wire.request_id,
            text: wire.text,
            emotion: wire.emotion,
            action: wire.action,
        })
    }

    fn send_raw(&self, line: &str) -> Result<(), String> {
        if let Some(stdin) = &self.stdin {
            let mut stdin = stdin.lock().map_err(|e| format!("Lock error: {}", e))?;
            writeln!(stdin, "{}", line).map_err(|e| format!("Write error: {}", e))?;
            stdin.flush().map_err(|e| format!("Flush error: {}", e))?;
            Ok(())
        } else {
            Err("Stdin not available".to_string())
        }
    }

    fn read_response(&self) -> Result<String, String> {
        if let Some(stdout) = &self.stdout {
            let mut stdout = stdout.lock().map_err(|e| format!("Lock error: {}", e))?;
            let mut line = String::new();
            stdout
                .read_line(&mut line)
                .map_err(|e| format!("Read error: {}", e))?;
            Ok(line.trim().to_string())
        } else {
            Err("Stdout not available".to_string())
        }
    }

    pub fn is_running(&self) -> bool {
        self.running
    }

    pub fn shutdown(&mut self) {
        if let Some(stdin) = &self.stdin {
            if let Ok(mut stdin) = stdin.lock() {
                let _ = writeln!(stdin, r#"{{"type":"shutdown"}}"#);
                let _ = stdin.flush();
            }
        }
        if let Some(mut process) = self.process.take() {
            let _ = process.wait();
        }
        self.running = false;
        self.stdin = None;
        self.stdout = None;
    }
}

impl Drop for PythonBridge {
    fn drop(&mut self) {
        self.shutdown();
    }
}

// Wire-форматы для JSON
#[derive(serde::Serialize)]
struct RequestWire {
    request_id: u64,
    request_type: String,
    text: String,
    pony_name: String,
    pony_personality: Option<String>,
    context: Vec<String>,
    available_actions: Vec<String>,
    language: String,
}

#[derive(serde::Deserialize)]
struct ResponseWire {
    request_id: u64,
    text: String,
    emotion: Option<String>,
    action: Option<String>,
}