// src_rust/main.rs
use winit::{
    event::WindowEvent,
    event_loop::EventLoop,
    application::ApplicationHandler,
    window::{WindowAttributes, WindowId},
    dpi::LogicalSize,
};
use wry::WebViewBuilder;
use std::sync::{Arc, Mutex};
use serde::Serialize;

mod loader;
mod window_manager;
mod pony;
mod pony_factory;
mod world;
mod renderer;
mod mesh;
mod texture;
mod shaders;
mod skeleton;
mod animation;
mod verlet;
mod math;
mod interaction;

use loader::DesktopPoniesLoader;
use window_manager::PonyWindow;

#[derive(Serialize)]
struct PonyMenuEntry {
    name: String,
    behaviors: Vec<String>,
    speaks_count: usize,
}

fn main() {
    let event_loop = EventLoop::new().unwrap();

    let mut loader = DesktopPoniesLoader::new(".");
    let menu_entries: Vec<PonyMenuEntry> = match loader.load_all() {
        Ok(()) => loader.configs.iter().map(|c| PonyMenuEntry {
            name: c.name.clone(),
            behaviors: c.behaviors.iter().map(|b| b.name.clone()).collect(),
            speaks_count: c.speaks.len(),
        }).collect(),
        Err(e) => {
            eprintln!("Loader error: {}", e);
            vec![]
        }
    };
    println!("Total ponies: {}", menu_entries.len());

    let ponies_json = serde_json::to_string(&menu_entries).unwrap();
    let html = build_html(&ponies_json);

    let mut app = App {
        ui_window: None,
        webview: None,
        pony_window: None,
        html: Some(html),
        spawn_queue: Arc::new(Mutex::new(Vec::new())),
    };

    event_loop.run_app(&mut app).unwrap();
}

fn build_html(ponies_json: &str) -> String {
    let css = include_str!("../src-ui/style.css");
    let js = include_str!("../src-ui/app.js");
    let html = include_str!("../src-ui/index.html");

    let patched_js = format!(
        "const PONIES_DATA = {{ ponies: {ponies_json} }};\n{js}"
    );

    html.replace("<link rel=\"stylesheet\" href=\"style.css\">",
                 &format!("<style>{css}</style>"))
        .replace("<script src=\"app.js\"></script>",
                 &format!("<script>{patched_js}</script>"))
}

struct App {
    ui_window: Option<Arc<winit::window::Window>>,
    webview: Option<wry::WebView>,
    pony_window: Option<Arc<Mutex<PonyWindow>>>,
    html: Option<String>,
    spawn_queue: Arc<Mutex<Vec<String>>>,
}

impl ApplicationHandler for App {
    fn resumed(&mut self, event_loop: &winit::event_loop::ActiveEventLoop) {
        // Создаём UI окно только если его ещё нет и нет окна пони
        if self.ui_window.is_none() && self.pony_window.is_none() {
            let ui_attrs = WindowAttributes::default()
                .with_title("Desktop Ponies — Select Pony")
                .with_inner_size(LogicalSize::new(420.0, 720.0))
                .with_transparent(false)
                .with_decorations(true)
                .with_resizable(false);

            let ui_window = Arc::new(event_loop.create_window(ui_attrs).unwrap());
            ui_window.set_visible(true);

            let spawn_q = self.spawn_queue.clone();
            let ui_window_clone = ui_window.clone();
            let html = self.html.take().unwrap();

            let webview = WebViewBuilder::new()
                .with_html(&html)
                .with_ipc_handler(move |msg| {
                    let body = msg.body().to_string();
                    println!("IPC: '{}'", body);
                    if let Some(name) = body.strip_prefix("spawn:") {
                        spawn_q.lock().unwrap().push(name.to_string());
                        ui_window_clone.request_redraw();
                    }
                })
                .build(&*ui_window)
                .unwrap();

            self.ui_window = Some(ui_window);
            self.webview = Some(webview);
            println!("UI ready. Select a pony and click Spawn.");
        }
    }

    fn window_event(
        &mut self,
        event_loop: &winit::event_loop::ActiveEventLoop,
        window_id: WindowId,
        event: WindowEvent,
    ) {
        match event {
            WindowEvent::CloseRequested => {
                // Закрытие UI окна = выход
                if self.ui_window.as_ref().map(|w| w.id()) == Some(window_id) {
                    println!("UI closed, exiting...");
                    event_loop.exit();
                }
            }
            WindowEvent::RedrawRequested => {
                let ui_id = self.ui_window.as_ref().map(|w| w.id());

                if Some(window_id) == ui_id {
                    // Redraw от UI окна — проверяем спавн
                    let names: Vec<String> = self.spawn_queue.lock().unwrap().drain(..).collect();

                    if !names.is_empty() {
                        // Закрываем UI окно
                        println!("Closing UI window...");
                        self.webview = None; // Дропаем WebView первым
                        self.ui_window = None; // Потом окно

                        // Создаём прозрачное окно с пони
                        let mut pw = PonyWindow::new();
                        pw.create_window(event_loop);

                        if let Some(w) = &pw.window {
                            w.set_visible(true);
                        }

                        for name in names {
                            pw.spawn_pony(&name);
                        }

                        pw.update_and_render();
                        if let Some(w) = &pw.window {
                            w.request_redraw();
                        }

                        self.pony_window = Some(Arc::new(Mutex::new(pw)));
                        println!("Pony window created! UI closed.");
                    }
                }

                // Рендерим окно пони
                if let Some(pw) = &self.pony_window {
                    if let Ok(mut pw) = pw.lock() {
                        pw.update_and_render();
                        if let Some(w) = &pw.window {
                            w.request_redraw();
                        }
                    }
                }
            }
            _ => {}
        }
    }
}