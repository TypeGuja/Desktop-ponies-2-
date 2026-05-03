// src_rust/main.rs
#[cfg(windows)]
#[link(name = "advapi32")]
#[link(name = "ole32")]
#[link(name = "user32")]
#[link(name = "shell32")]
extern "C" {}

use std::fs;
use std::sync::{Arc, Mutex};
use std::net::TcpListener;
use std::io::{Read, Write};
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

    let patched_js = format!(
        "const PONIES_DATA = {{ ponies: {ponies_json} }};\n{js}"
    );

    let full_html = html_template
        .replace("<link rel=\"stylesheet\" href=\"style.css\">", &format!("<style>{css}</style>"))
        .replace("<script src=\"app.js\"></script>", &format!("<script>{patched_js}</script>"));

    // Мини-HTTP сервер
    let listener = TcpListener::bind("127.0.0.1:0").expect("Failed to bind");
    let port = listener.local_addr().unwrap().port();

    let html_data = Arc::new(full_html);
    let html_clone = html_data.clone();

    std::thread::spawn(move || {
        for mut stream in listener.incoming().flatten() {
            let mut buffer = [0u8; 4096];
            let _ = stream.read(&mut buffer); // Читаем запрос

            let response = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                html_clone.len(),
                html_clone.as_str()
            );
            let _ = stream.write_all(response.as_bytes());
        }
    });

    let url = format!("http://127.0.0.1:{}", port);
    println!("Server: {}", url);

    let event_loop = EventLoop::new();

    let window = WindowBuilder::new()
        .with_title("Desktop Ponies")
        .with_inner_size(tao::dpi::LogicalSize::new(420.0, 720.0))
        .with_resizable(true)
        .build(&event_loop)
        .unwrap();

    let mut pony_window = PonyWindow::new();
    pony_window.create_window(&event_loop);
    if let Some(w) = &pony_window.window {
        w.set_visible(false);
    }

    let pony_window = Arc::new(Mutex::new(pony_window));
    let pony_window_clone = pony_window.clone();

    let _webview = WebViewBuilder::new()
        .with_url(&url)
        .with_ipc_handler(move |request| {
            let body = request.body();
            println!("IPC: {}", body);

            if let Some(name) = body.strip_prefix("spawn:") {
                if let Ok(mut pw) = pony_window_clone.lock() {
                    if let Some(w) = &pw.window {
                        w.set_visible(true);
                    }
                    pw.spawn_pony(name);
                }
            }
        })
        .build(&window)
        .unwrap();

    println!("Ready! Select a pony and click Spawn.");

    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Poll;

        match event {
            Event::WindowEvent {
                event: WindowEvent::CloseRequested,
                window_id, ..
            } => {
                if window_id == window.id() {
                    *control_flow = ControlFlow::Exit;
                }
            }
            Event::RedrawRequested(_) | Event::MainEventsCleared => {
                if let Ok(mut pw) = pony_window.lock() {
                    pw.update_and_render();
                }
            }
            _ => {}
        }
    });
}