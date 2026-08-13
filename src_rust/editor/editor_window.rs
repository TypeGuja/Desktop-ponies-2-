// src_rust/editor/editor_window.rs

use std::sync::{Arc, Mutex, mpsc};
use std::path::PathBuf;
use wry::{WebView, WebViewBuilder};
use winit::window::Window;
use rust_embed::Embed;
use crate::loader::DesktopPoniesLoader;
use crate::editor::editor_handlers::handle_ipc;

#[derive(Embed)]
#[folder = "src_uiEditor/"]
struct UiAssets;

pub struct EditorWindow {
    pub window: Arc<Window>,
    pub webview: WebView,
    pub sender: mpsc::Sender<String>,
    pub receiver: mpsc::Receiver<String>,
}

impl EditorWindow {
    pub fn from_window(
        window: Arc<Window>,
        loader: Arc<Mutex<DesktopPoniesLoader>>,
        ponies_dir: PathBuf,
    ) -> Result<Self, String> {
        let html = build_editor_html();

        let (tx_to_webview, rx_from_rust) = mpsc::channel();
        let (tx_to_rust, rx_from_webview) = mpsc::channel();

        let loader_clone = loader.clone();
        let ponies_dir_clone = ponies_dir.clone();
        let tx_to_rust_clone = tx_to_rust.clone();
        let tx_to_webview_clone = tx_to_webview.clone();

        // КЛЮЧЕВОЕ: используем with_custom_protocol для правильной IPC
        let webview = WebViewBuilder::new()
            .with_html(&html)
            .with_ipc_handler(move |request| {
                let body = request.body();
                println!("[Editor] IPC received: {}", body);
                let _ = tx_to_rust_clone.send(body.to_string());
            })
            .build(&*window)
            .map_err(|e| format!("Failed to build webview: {}", e))?;

        window.set_visible(true);

        // Поток для обработки сообщений из WebView
        std::thread::spawn(move || {
            for msg in rx_from_webview {
                handle_ipc(&msg, &loader_clone, &ponies_dir_clone, &tx_to_webview_clone);
            }
        });

        Ok(Self {
            window,
            webview,
            sender: tx_to_webview,
            receiver: rx_from_rust,
        })
    }

    pub fn send_to_webview(&self, message: &str) {
        // Экранируем сообщение для JavaScript
        let escaped = message
            .replace('\\', "\\\\")
            .replace('\'', "\\'")
            .replace('"', "\\\"")
            .replace('\n', "\\n")
            .replace('\r', "\\r");

        let js = format!(
            "(function() {{
                try {{
                    console.log('[Editor] Received from Rust:', '{}');
                    if (window.editorReceive) {{
                        window.editorReceive('{}');
                    }} else {{
                        console.error('[Editor] window.editorReceive not found');
                    }}
                }} catch(e) {{
                    console.error('[Editor] Error:', e);
                }}
            }})();",
            escaped, escaped
        );

        // ИСПРАВЛЕНО: срез по байтовому индексу мог упасть посреди
        // многобайтового UTF-8 символа (например, кириллицы в тексте пони)
        // и вызвать панику "byte index is not a char boundary".
        let mut cut = message.len().min(200);
        while cut > 0 && !message.is_char_boundary(cut) {
            cut -= 1;
        }
        println!("[Editor] Sending to WebView: {}", &message[..cut]);
        let _ = self.webview.evaluate_script(&js);
    }

    pub fn process_messages(&mut self) {
        while let Ok(msg) = self.receiver.try_recv() {
            self.send_to_webview(&msg);
        }
    }
}

fn build_editor_html() -> String {
    // Загружаем index.html из встроенных ресурсов
    let index_asset = UiAssets::get("index.html");
    if index_asset.is_none() {
        eprintln!("[Editor] ERROR: index.html not found in embedded assets!");
        return create_fallback_html();
    }

    let html_content = String::from_utf8_lossy(&index_asset.unwrap().data).to_string();

    // Собираем все CSS файлы
    let mut css_all = String::new();
    let css_files = ["css/base.css", "css/layout.css", "css/components.css", "css/editor.css", "css/dialogs.css"];
    for css_file in css_files {
        if let Some(asset) = UiAssets::get(css_file) {
            let content = String::from_utf8_lossy(&asset.data);
            css_all.push_str(&format!("<style>{}</style>", content));
            println!("[Editor] Embedded CSS: {}", css_file);
        }
    }

    // Собираем все JS файлы
    let mut js_all = String::new();
    let js_files = [
        "js/utils.js", "js/api.js", "js/state.js", "js/pony_list.js", "js/pony_editor.js",
        "js/behavior_editor.js", "js/speech_editor.js", "js/effect_editor.js",
        "js/interaction_editor.js", "js/dialogs.js", "js/main.js"
    ];
    for js_file in js_files {
        if let Some(asset) = UiAssets::get(js_file) {
            let content = String::from_utf8_lossy(&asset.data);
            js_all.push_str(&format!("<script>{}</script>", content));
            println!("[Editor] Embedded JS: {}", js_file);
        }
    }

    // Регистрация IPC - ВАЖНО: правильная инициализация
    let register_script = r#"
    <script>
    console.log('[Editor] Initializing IPC...');

    // Функция для отправки сообщений в Rust
    window.sendToRust = function(message) {
        console.log('[Editor] sendToRust called:', message);
        if (window.ipc && window.ipc.postMessage) {
            window.ipc.postMessage(message);
        } else if (window.external && typeof window.external.sendMessage === 'function') {
            window.external.sendMessage(message);
        } else {
            console.error('[Editor] No IPC handler found');
        }
    };

    // Функция для получения сообщений от Rust
    window.editorReceive = function(message) {
        console.log('[Editor] editorReceive called, raw:', message);
        try {
            const data = JSON.parse(message);
            console.log('[Editor] Parsed message type:', data.type);

            // Обновляем EditorAPI если он существует
            if (window.EditorAPI && window.EditorAPI._handleMessage) {
                window.EditorAPI._handleMessage(data);
            }

            // Вызываем глобальный обработчик
            if (window.handleEditorMessage) {
                window.handleEditorMessage(data);
            }
        } catch(e) {
            console.error('[Editor] Failed to parse message:', e);
        }
    };

    // Убеждаемся что EditorAPI получает сообщения
    window.handleEditorMessage = function(data) {
        console.log('[Editor] handleEditorMessage:', data.type);

        switch(data.type) {
            case 'ponies_list':
                console.log('[Editor] Ponies list received, count:', data.data?.length);
                if (window.PonyList && window.PonyList.updateList) {
                    window.PonyList.updateList(data.data);
                }
                break;
            case 'pony_config':
                console.log('[Editor] Pony config received:', data.pony_name);
                if (window.EditorState && window.EditorState.setPony) {
                    window.EditorState.setPony(data.pony_name, data.data);
                }
                if (window.PonyEditor && window.PonyEditor.render) {
                    window.PonyEditor.render(data.data);
                }
                break;
            default:
                console.log('[Editor] Unknown message type:', data.type);
        }
    };

    // Загружаем пони после инициализации
    setTimeout(function() {
        console.log('[Editor] WebView ready, loading ponies...');
        if (window.EditorAPI && window.EditorAPI.loadPonies) {
            window.EditorAPI.loadPonies();
        } else if (window.sendToRust) {
            window.sendToRust('editor:load_ponies');
        } else {
            console.error('[Editor] Cannot load ponies - no API');
        }
    }, 1000);

    console.log('[Editor] Initialization complete');
    </script>
    "#;

    let result = html_content
        .replace("<!-- INJECT_CSS -->", &css_all)
        .replace("<!-- INJECT_JS -->", &(register_script.to_string() + &js_all));

    result
}

fn create_fallback_html() -> String {
    r#"
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Pony Editor</title>
    <style>
        body{background:#1e1e2e;color:#cdd6f4;font-family:monospace;padding:20px}
        .error{color:#f38ba8;border:1px solid #f38ba8;padding:20px;border-radius:8px}
        button{background:#cba6f7;border:none;padding:10px 20px;border-radius:8px;cursor:pointer}
        #ponies{max-height:300px;overflow-y:auto;margin-top:20px}
        .pony-item{padding:5px;margin:2px;background:#313244;border-radius:4px}
    </style>
    </head>
    <body>
    <div class="error">
        <h2>⚠️ Pony Editor</h2>
        <p>Loading...</p>
        <button onclick="window.sendToRust('editor:load_ponies')">Load Ponies</button>
        <div id="ponies"></div>
    </div>
    <script>
    window.sendToRust = function(m){
        console.log('Sending:', m);
        if(window.ipc) window.ipc.postMessage(m);
    };
    window.editorReceive = function(m){
        console.log('Received:', m);
        try{
            const d=JSON.parse(m);
            if(d.type==='ponies_list'){
                const div=document.getElementById('ponies');
                div.innerHTML='<h3>'+d.data.length+' ponies loaded</h3>';
                d.data.forEach(p=>{
                    const item=document.createElement('div');
                    item.className='pony-item';
                    item.textContent=p;
                    div.appendChild(item);
                });
            }
        }catch(e){}
    };
    setTimeout(()=>{
        if(window.sendToRust) window.sendToRust('editor:load_ponies');
    },500);
    </script>
    </body>
    </html>
    "#.to_string()
}