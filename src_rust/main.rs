// src_rust/main.rs
#[cfg(windows)]
#[link(name = "advapi32")]
#[link(name = "ole32")]
#[link(name = "user32")]
#[link(name = "shell32")]
extern "C" {}

use std::fs;
use std::sync::{Arc, Mutex};
use serde::Serialize;
use tao::{
    event::{Event, WindowEvent},
    event_loop::{ControlFlow, EventLoop},
    window::WindowBuilder,
};
use wry::WebViewBuilder;

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

    let html_template = include_str!("../src-ui/index.html");
    let css = include_str!("../src-ui/style.css");
    let js = include_str!("../src-ui/app.js");

    // Вставляем данные прямо в начало JS
    let patched_js = format!(
        "const PONIES_DATA = {{ ponies: {ponies_json} }};\n{js}"
    );

    let full_html = html_template
        .replace("<link rel=\"stylesheet\" href=\"style.css\">", &format!("<style>{css}</style>"))
        .replace("<script src=\"app.js\"></script>", &format!("<script>{patched_js}</script>"));

    let temp_dir = std::env::temp_dir();
    let html_path = temp_dir.join("desktop_ponies_ui.html");
    fs::write(&html_path, &full_html).expect("Failed to write temp HTML");

    let event_loop = EventLoop::new();

    // Главное окно-меню
    let window = WindowBuilder::new()
        .with_title("Desktop Ponies")
        .with_inner_size(tao::dpi::LogicalSize::new(420.0, 720.0))
        .with_resizable(true)
        .build(&event_loop)
        .unwrap();

    let url = format!("file:///{}", html_path.to_string_lossy().replace('\\', "/"));
    println!("Loading menu: {}", url);

    // Очередь спавна
    let spawn_queue: Arc<Mutex<Vec<String>>> = Arc::new(Mutex::new(Vec::new()));
    let spawn_queue_clone = spawn_queue.clone();

    let _webview = WebViewBuilder::new()
        .with_url(&url)
        .with_ipc_handler(move |request| {
            let msg = request.body();
            if let Ok(cmd) = serde_json::from_str::<serde_json::Value>(msg) {
                if cmd["action"] == "spawn" {
                    let name = cmd["name"].as_str().unwrap_or("").to_string();
                    println!("IPC: spawn {}", name);
                    if let Ok(mut q) = spawn_queue_clone.lock() {
                        q.push(name);
                    }
                }
            }
        })
        .build(&window)
        .unwrap();

    // Окно с пони — создаём ПОСЛЕ главного окна
    let mut pony_window = PonyWindow::new();
    pony_window.create_window(&event_loop);

    println!("Both windows ready!");

    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Poll;

        match event {
            Event::WindowEvent {
                event: WindowEvent::CloseRequested,
                window_id, .. } => {
                // Закрываем всё при закрытии главного окна
                if window_id == window.id() {
                    *control_flow = ControlFlow::Exit;
                }
            }
            Event::RedrawRequested(_) | Event::MainEventsCleared => {
                // Обрабатываем очередь спавна
                if let Ok(mut q) = spawn_queue.lock() {
                    for name in q.drain(..) {
                        pony_window.spawn_pony(&name);
                    }
                }
                // Обновляем пони
                pony_window.update_and_render();
            }
            _ => {}
        }
    });
}