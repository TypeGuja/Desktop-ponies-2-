// src_rust/monitor_manager.rs
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use winit::event_loop::ActiveEventLoop;
use winit::monitor::MonitorHandle;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MonitorInfo {
    pub name: String,
    pub id: String,
    pub width: u32,
    pub height: u32,
    pub x: i32,
    pub y: i32,
    pub refresh_rate_millihertz: Option<u32>,
    pub scale_factor: f64,
    pub is_primary: bool,
}

pub struct MonitorManager {
    pub monitors: Vec<MonitorInfo>,
    pub selected_ids: Vec<String>,
    id_to_index: HashMap<String, usize>,
}

impl MonitorManager {
    pub fn new() -> Self {
        Self {
            monitors: Vec::new(),
            selected_ids: Vec::new(),
            id_to_index: HashMap::new(),
        }
    }

    pub fn detect(&mut self, event_loop: &ActiveEventLoop) {
        self.monitors.clear();
        self.id_to_index.clear();

        let available_monitors: Vec<MonitorHandle> = event_loop.available_monitors().collect();

        // Определяем primary монитор
        let primary_name = event_loop.primary_monitor()
            .and_then(|m| m.name())
            .unwrap_or_default();

        // ИСПРАВЛЕНО: раньше ID монитора был просто "monitor_{index}", хотя
        // комментарий обещал "стабильный ID из имени". Индекс в перечислении
        // мониторов не стабилен между перезапусками (при отключении/смене
        // порядка мониторов), из-за чего сохранённый в настройках выбор
        // мониторов после переподключения мог применяться не к тем экранам.
        // Теперь ID строится из имени монитора, а дубликаты (несколько
        // одинаковых моделей) получают числовой суффикс.
        let mut name_counts: HashMap<String, usize> = HashMap::new();

        for (index, monitor) in available_monitors.iter().enumerate() {
            let name = monitor.name().unwrap_or_else(|| format!("Monitor {}", index + 1));
            let size = monitor.size();
            let position = monitor.position();
            let scale = monitor.scale_factor();

            let slug: String = name.chars()
                .map(|c| if c.is_alphanumeric() { c.to_ascii_lowercase() } else { '_' })
                .collect();
            let occurrence = name_counts.entry(slug.clone()).or_insert(0);
            let id = if *occurrence == 0 {
                format!("monitor_{}", slug)
            } else {
                format!("monitor_{}_{}", slug, occurrence)
            };
            *occurrence += 1;

            let is_primary = name == primary_name;

            self.monitors.push(MonitorInfo {
                name,
                id: id.clone(),
                width: size.width,
                height: size.height,
                x: position.x,
                y: position.y,
                refresh_rate_millihertz: monitor.refresh_rate_millihertz(),
                scale_factor: scale,
                is_primary,
            });
            self.id_to_index.insert(id, index);
        }

        // Если selected_ids пуст - выбираем все
        if self.selected_ids.is_empty() {
            self.selected_ids = self.monitors.iter().map(|m| m.id.clone()).collect();
        }

        println!("[MonitorManager] Detected {} monitor(s):", self.monitors.len());
        for m in &self.monitors {
            println!("  {} (id={}) {}x{} at ({},{}) scale={:.1}{}",
                     m.name, m.id, m.width, m.height, m.x, m.y, m.scale_factor,
                     if m.is_primary { " [PRIMARY]" } else { "" });
        }
    }

    pub fn get(&self, index: usize) -> Option<&MonitorInfo> {
        self.monitors.get(index)
    }

    pub fn get_by_id(&self, id: &str) -> Option<&MonitorInfo> {
        self.id_to_index.get(id).and_then(|&i| self.monitors.get(i))
    }

    pub fn to_json_value(&self) -> serde_json::Value {
        serde_json::json!({
            "monitors": &self.monitors,
        })
    }
}