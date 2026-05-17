// src_rust/editor/editor_window.rs

use std::sync::{Arc, Mutex};
use std::path::PathBuf;
use wry::{WebView, WebViewBuilder, WebViewAttributes};
use winit::window::{Window, WindowAttributes, WindowLevel};
use winit::dpi::LogicalSize;

use crate::loader::DesktopPoniesLoader;

pub struct EditorWindow {
    pub window: Arc<Window>,
    pub webview: WebView,
}

impl EditorWindow {
    pub fn from_window(
        window: Arc<Window>,
        loader: Arc<Mutex<DesktopPoniesLoader>>,
        ponies_dir: PathBuf,
    ) -> Result<Self, String> {
        let html = build_editor_html();

        // Для отладки - сохраним HTML в файл
        if let Ok(mut file) = std::fs::File::create("debug_editor.html") {
            use std::io::Write;
            let _ = file.write_all(html.as_bytes());
            println!("[Editor] Saved debug HTML to debug_editor.html");
        }

        println!("[Editor] HTML length: {} bytes", html.len());

        let loader_clone = loader.clone();
        let ponies_dir_clone = ponies_dir.clone();

        // Создаем webview с обработчиком IPC
        let webview = WebViewBuilder::new()
            .with_html(&html)
            .with_ipc_handler(move |request| {
                let body = request.body();
                println!("[Editor] IPC received: {}", body);

                // Для отправки ответа нужен webview, но мы не можем его захватить здесь
                // Поэтому используем глобальный канал или сохраняем в статику
                // Пока просто вызываем обработчик, который будет отправлять через callback
                handle_ipc(body, &loader_clone, &ponies_dir_clone);
            })
            .build(&*window)
            .map_err(|e| format!("Failed to build webview: {}", e))?;

        window.set_visible(true);

        Ok(Self { window, webview })
    }

    pub fn new(
        event_loop: &winit::event_loop::ActiveEventLoop,
        loader: Arc<Mutex<DesktopPoniesLoader>>,
        ponies_dir: PathBuf,
    ) -> Result<Self, String> {
        let attrs = WindowAttributes::default()
            .with_title("Pony Editor - Desktop Ponies")
            .with_inner_size(LogicalSize::new(1100, 750))
            .with_min_inner_size(LogicalSize::new(900, 600))
            .with_window_level(WindowLevel::AlwaysOnTop);

        let window = Arc::new(
            event_loop.create_window(attrs)
                .map_err(|e| format!("Failed to create editor window: {}", e))?
        );

        Self::from_window(window, loader, ponies_dir)
    }
}

// Глобальный WebView для отправки сообщений (костыль, но работает)
// В production лучше использовать каналы
static mut CURRENT_WEBVIEW: Option<*mut wry::WebView> = None;

pub fn set_webview(webview: &WebView) {
    unsafe {
        CURRENT_WEBVIEW = Some(webview as *const _ as *mut _);
    }
}

pub fn send_to_webview(message: &str) {
    unsafe {
        if let Some(wv_ptr) = CURRENT_WEBVIEW {
            if let Some(webview) = (wv_ptr as *mut WebView).as_mut() {
                let js = format!(
                    "if(window.editorReceive) window.editorReceive('{}');",
                    message.replace('\'', "\\'").replace('\n', "\\n")
                );
                let _ = webview.evaluate_script(&js);
            }
        }
    }
}

fn handle_ipc(body: &str, loader: &Arc<Mutex<DesktopPoniesLoader>>, ponies_dir: &PathBuf) {
    if body == "editor:load_ponies" {
        send_ponies_list(loader);
    } else if let Some(pony_name) = body.strip_prefix("editor:load_pony:") {
        send_pony_config(loader, pony_name);
    } else if let Some(data) = body.strip_prefix("editor:save_pony:") {
        save_pony_config(data, ponies_dir);
    } else if body == "editor:close" {
        println!("[Editor] Close request received");
    } else {
        println!("[Editor] Unknown IPC: {}", body);
    }
}

fn send_ponies_list(loader: &Arc<Mutex<DesktopPoniesLoader>>) {
    let loader = loader.lock().unwrap();
    let ponies: Vec<String> = loader.configs.iter()
        .map(|c| c.name.clone())
        .collect();

    let response = serde_json::json!({
        "type": "ponies_list",
        "data": ponies
    });

    println!("[Editor] Sending ponies list ({} ponies)", ponies.len());
    send_to_webview(&response.to_string());
}

fn send_pony_config(loader: &Arc<Mutex<DesktopPoniesLoader>>, pony_name: &str) {
    let loader = loader.lock().unwrap();
    if let Some(config) = loader.get_config(pony_name) {
        let behaviors: Vec<serde_json::Value> = config.behaviors.iter().map(|b| {
            serde_json::json!({
                "name": b.name,
                "probability": b.probability,
                "min_duration": b.min_duration,
                "max_duration": b.max_duration,
                "speed": b.speed,
                "sprite_right": b.sprite_right,
                "sprite_left": b.sprite_left,
                "movement": b.movement,
                "linked_behavior": b.linked_behavior,
                "skip": b.skip,
                "group": b.group,
            })
        }).collect();

        let speaks: Vec<serde_json::Value> = config.speaks.iter().map(|s| {
            serde_json::json!({
                "name": s.name,
                "text": s.text,
                "sound_files": s.sound_files,
                "skip": s.skip,
                "frequency": s.frequency,
            })
        }).collect();

        let interactions: Vec<serde_json::Value> = config.interactions.iter().map(|i| {
            serde_json::json!({
                "name": i.name,
                "probability": i.probability,
                "cooldown": i.cooldown,
                "targets": i.targets,
                "target_count": i.target_count,
                "behaviors": i.behaviors,
                "duration": i.duration,
            })
        }).collect();

        let effects: Vec<serde_json::Value> = config.effects.iter().map(|e| {
            serde_json::json!({
                "name": e.name,
                "linked": e.linked,
                "sprite_right": e.sprite_right,
                "sprite_left": e.sprite_left,
                "duration": e.duration,
                "delay": e.delay,
            })
        }).collect();

        let response = serde_json::json!({
            "type": "pony_config",
            "pony_name": pony_name,
            "data": {
                "name": config.name,
                "categories": config.categories,
                "behaviors": behaviors,
                "speaks": speaks,
                "interactions": interactions,
                "effects": effects,
            }
        });

        println!("[Editor] Sending config for pony: {}", pony_name);
        send_to_webview(&response.to_string());
    } else {
        let response = serde_json::json!({
            "type": "error",
            "message": format!("Pony '{}' not found", pony_name)
        });
        println!("[Editor] Pony not found: {}", pony_name);
        send_to_webview(&response.to_string());
    }
}

fn save_pony_config(data: &str, ponies_dir: &PathBuf) {
    println!("[Editor] Saving pony config, data length: {}", data.len());

    if let Ok(config_data) = serde_json::from_str::<serde_json::Value>(data) {
        let pony_name = config_data["name"].as_str().unwrap_or("unknown");
        println!("[Editor] Saving pony config for: {}", pony_name);

        // TODO: реальное сохранение в файл
        // Здесь нужно будет использовать ini_writer::write_pony_config

        let response = serde_json::json!({
            "type": "save_success",
            "message": format!("Pony '{}' saved successfully", pony_name)
        });
        send_to_webview(&response.to_string());
    } else {
        eprintln!("[Editor] Failed to parse config data: {}", data);
        let response = serde_json::json!({
            "type": "save_error",
            "message": "Failed to parse config data"
        });
        send_to_webview(&response.to_string());
    }
}

fn build_editor_html() -> String {
    // Загружаем HTML
    let html_content = match std::fs::read_to_string("src_uiEditor/index.html") {
        Ok(content) => content,
        Err(e) => {
            eprintln!("[Editor] FATAL: Failed to read index.html: {}", e);
            panic!("Cannot start editor: index.html not found at src_uiEditor/index.html");
        }
    };

    // Загружаем CSS файлы
    let mut css_all = String::new();
    let css_files = [
        "src_uiEditor/css/base.css",
        "src_uiEditor/css/layout.css",
        "src_uiEditor/css/components.css",
        "src_uiEditor/css/editor.css"
    ];

    for path in css_files {
        match std::fs::read_to_string(path) {
            Ok(content) => {
                css_all.push_str(&format!("<style>{}</style>", content));
                println!("[Editor] Loaded CSS: {}", path);
            }
            Err(e) => {
                eprintln!("[Editor] FATAL: Failed to read CSS {}: {}", path, e);
                panic!("Cannot start editor: CSS file missing at {}", path);
            }
        }
    }

    // Загружаем JS файлы
    let mut js_all = String::new();
    let js_files = [
        "src_uiEditor/js/utils.js",
        "src_uiEditor/js/api.js",
        "src_uiEditor/js/state.js",
        "src_uiEditor/js/pony_list.js",
        "src_uiEditor/js/pony_editor.js",
        "src_uiEditor/js/behavior_editor.js",
        "src_uiEditor/js/speech_editor.js",
        "src_uiEditor/js/effect_editor.js",
        "src_uiEditor/js/interaction_editor.js",
        "src_uiEditor/js/main.js"
    ];

    for path in js_files {
        match std::fs::read_to_string(path) {
            Ok(content) => {
                js_all.push_str(&format!("<script>{}</script>", content));
                println!("[Editor] Loaded JS: {}", path);
            }
            Err(e) => {
                eprintln!("[Editor] FATAL: Failed to read JS {}: {}", path, e);
                panic!("Cannot start editor: JS file missing at {}", path);
            }
        }
    }

    // Добавляем код для регистрации WebView
    let register_script = r#"
    <script>
    // Регистрируем WebView для получения сообщений
    window.__editorReady = true;
    console.log('[Editor] WebView ready, looking for ipc...');

    // Пробуем разные способы получения IPC
    if (typeof window.external !== 'undefined' && window.external) {
        window.ipc = window.external;
        console.log('[Editor] IPC via external');
    }

    // Сообщаем Rust, что мы готовы
    setTimeout(() => {
        if (window.ipc && window.ipc.postMessage) {
            window.ipc.postMessage('editor:ready');
        } else if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.ipc) {
            window.webkit.messageHandlers.ipc.postMessage('editor:ready');
        }
    }, 100);
    </script>
    "#;

    // Инжектим CSS, JS и регистрацию в HTML
    let result = html_content
        .replace("<!-- INJECT_CSS -->", &css_all)
        .replace("<!-- INJECT_JS -->", &(register_script.to_string() + &js_all));

    println!("[Editor] Final HTML length: {} bytes", result.len());
    println!("[Editor] CSS injected: {} chars, JS injected: {} chars", css_all.len(), js_all.len() + register_script.len());

    // Сохраняем для отладки
    if let Ok(mut file) = std::fs::File::create("debug_editor.html") {
        use std::io::Write;
        let _ = file.write_all(result.as_bytes());
        println!("[Editor] Saved debug HTML to debug_editor.html");
    }

    result
}