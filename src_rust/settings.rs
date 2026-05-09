// src_rust/settings.rs
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs;
use std::path::PathBuf;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AppSettings {
    pub selected_monitors: HashSet<String>,
    pub pony_limit: usize,
    pub spawn_on_start: Vec<String>,
    pub fps_limit: u32,  // ДОБАВИТЬ
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            selected_monitors: HashSet::new(),
            pony_limit: 50,
            spawn_on_start: vec![],
            fps_limit: 60,  // ДОБАВИТЬ (по умолчанию 60 FPS)
        }
    }
}

impl AppSettings {
    /// Загружает настройки из JSON-файла
    pub fn load(path: &PathBuf) -> Self {
        match fs::read_to_string(path) {
            Ok(content) => {
                match serde_json::from_str(&content) {
                    Ok(settings) => {
                        println!("[Settings] Loaded from {:?}", path);
                        settings
                    }
                    Err(e) => {
                        eprintln!("[Settings] Failed to parse: {}, using defaults", e);
                        Self::default()
                    }
                }
            }
            Err(_) => {
                println!("[Settings] No settings file found, using defaults");
                Self::default()
            }
        }
    }

    /// Сохраняет настройки в JSON-файл
    pub fn save(&self, path: &PathBuf) {
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        match serde_json::to_string_pretty(self) {
            Ok(json) => {
                if let Err(e) = fs::write(path, json) {
                    eprintln!("[Settings] Failed to save: {}", e);
                } else {
                    println!("[Settings] Saved to {:?}", path);
                }
            }
            Err(e) => eprintln!("[Settings] Serialization error: {}", e),
        }
    }
}