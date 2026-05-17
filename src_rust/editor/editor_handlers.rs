// src_rust/editor/editor_handlers.rs

use std::sync::{Arc, Mutex};
use std::path::PathBuf;
use serde_json::{json, Value};
use crate::loader::DesktopPoniesLoader;

pub struct EditorIpcHandler {
    loader: Arc<Mutex<DesktopPoniesLoader>>,
    ponies_dir: PathBuf,
}

impl EditorIpcHandler {
    pub fn new(loader: Arc<Mutex<DesktopPoniesLoader>>, ponies_dir: PathBuf) -> Self {
        Self { loader, ponies_dir }
    }

    pub fn handle(&self, body: &str) {
        if body == "editor:load_ponies" {
            self.send_ponies_list();
        } else if let Some(pony_name) = body.strip_prefix("editor:load_pony:") {
            self.send_pony_config(pony_name);
        } else if let Some(data) = body.strip_prefix("editor:save_pony:") {
            self.save_pony_config(data);
        } else {
            println!("[Editor] Unknown IPC: {}", body);
        }
    }

    fn send_ponies_list(&self) {
        let loader = self.loader.lock().unwrap();
        let ponies: Vec<String> = loader.configs.iter()
            .map(|c| c.name.clone())
            .collect();

        let response = json!({
            "type": "ponies_list",
            "data": ponies
        });

        // Отправляем в webview (нужно добавить callback)
        self.send_to_webview(&response.to_string());
    }

    fn send_pony_config(&self, pony_name: &str) {
        let loader = self.loader.lock().unwrap();
        if let Some(config) = loader.get_config(pony_name) {
            let response = json!({
                "type": "pony_config",
                "pony_name": pony_name,
                "data": {
                    "name": config.name,
                    "categories": config.categories,
                    "behaviors": config.behaviors,
                    "speaks": config.speaks,
                    "interactions": config.interactions,
                    "effects": config.effects,
                }
            });
            self.send_to_webview(&response.to_string());
        } else {
            let response = json!({
                "type": "error",
                "message": format!("Pony '{}' not found", pony_name)
            });
            self.send_to_webview(&response.to_string());
        }
    }

    fn save_pony_config(&self, data: &str) {
        if let Ok(config_data) = serde_json::from_str::<Value>(data) {
            // TODO: сохранить конфиг в файл
            println!("[Editor] Saving pony config: {}", config_data["name"].as_str().unwrap_or("unknown"));

            let response = json!({
                "type": "save_success",
                "message": "Pony saved successfully"
            });
            self.send_to_webview(&response.to_string());
        } else {
            let response = json!({
                "type": "save_error",
                "message": "Failed to parse config data"
            });
            self.send_to_webview(&response.to_string());
        }
    }

    fn send_to_webview(&self, message: &str) {
        // TODO: нужно хранить WebView и вызывать evaluate_script
        // Пока просто печатаем в консоль
        println!("[Editor] Would send to webview: {}", message);
    }
}