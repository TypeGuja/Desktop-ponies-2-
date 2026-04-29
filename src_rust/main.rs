// src_rust/main.rs
use std::sync::Mutex;
use serde::Serialize;
use tao::{
    event::{Event, WindowEvent},
    event_loop::{ControlFlow, EventLoop},
    window::WindowBuilder,
};
use wry::WebViewBuilder;
// src_rust/main.rs — в самый верх добавить
#[feature(link_args)] // только на nightly! Убери если stable

// Если stable:
#[cfg_attr(windows, link(name = "advapi32"))]
#[cfg_attr(windows, link(name = "ole32"))]
extern "C" {}

mod loader;
use loader::DesktopPoniesLoader;

#[derive(Serialize, Clone)]
struct PonyEntry {
    name: String,
    behaviors: Vec<String>,
    speaks_count: usize,
}

fn main() {
    let mut loader = DesktopPoniesLoader::new(".");
    let ponies: Vec<PonyEntry> = match loader.load_all() {
        Ok(()) => loader.configs.iter().map(|c| PonyEntry {
            name: c.name.clone(),
            behaviors: c.behaviors.iter().map(|b| b.name.clone()).collect(),
            speaks_count: c.speaks.len(),
        }).collect(),
        Err(e) => {
            eprintln!("Loader error: {}", e);
            vec![]
        }
    };

    let ponies_json = serde_json::to_string(&ponies).unwrap();

    let event_loop = EventLoop::new();
    let window = WindowBuilder::new()
        .with_title("Desktop Ponies")
        .with_inner_size(tao::dpi::LogicalSize::new(420.0, 720.0))
        .with_resizable(true)
        .build(&event_loop)
        .unwrap();

    let html = include_str!("../src-ui/index.html");
    let css = include_str!("../src-ui/style.css");
    let js = include_str!("../src-ui/app.js");

    let full_html = html
        .replace(
            "<link rel=\"stylesheet\" href=\"style.css\">",
            &format!("<style>{css}</style>")
        )
        .replace(
            "<script src=\"app.js\"></script>",
            &format!("<script>{js}</script>")
        )
        .replace(
            "const { invoke } = window.__TAURI__?.tauri || {};",
            &format!("const PONIES_DATA = {ponies_json};\nconst invoke = null;")
        );

    let _webview = WebViewBuilder::new()
        .with_html(full_html)
        .build(&window)
        .unwrap();

    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;
        if let Event::WindowEvent { event: WindowEvent::CloseRequested, .. } = event {
            *control_flow = ControlFlow::Exit;
        }
    });
}