#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
// src_rust/main.rs

mod app;

use desktop_ponies_lib::editor::EditorWindow;
use desktop_ponies_lib::loader::PonyCollection;
use std::sync::{Arc, Mutex};
use winit::application::ApplicationHandler;
use winit::dpi::LogicalSize;
use winit::event::WindowEvent;
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::window::{WindowAttributes, WindowId};

fn run_editor_mode() {
    #[derive(Debug, Clone)]
    enum EditorEvent {}

    let root = app::find_root();
    let ponies_dir = root.join("Ponies");
    // Редактор загружает и некорректные поведения, чтобы их можно было исправить.
    let collection = PonyCollection::load(&root, false);
    println!("[Editor] Loaded {} ponies", collection.bases.len());
    let loader = Arc::new(Mutex::new(collection));

    let event_loop = EventLoop::<EditorEvent>::with_user_event().build().expect("event loop");
    let attrs = WindowAttributes::default()
        .with_title("Pony Editor - Desktop Ponies")
        .with_inner_size(LogicalSize::new(1180.0, 780.0))
        .with_min_inner_size(LogicalSize::new(900.0, 600.0));
    let window = Arc::new(event_loop.create_window(attrs).expect("editor window"));

    struct EditorApp {
        editor: EditorWindow,
    }
    impl ApplicationHandler<EditorEvent> for EditorApp {
        fn resumed(&mut self, event_loop: &ActiveEventLoop) {
            event_loop.set_control_flow(ControlFlow::WaitUntil(std::time::Instant::now() + std::time::Duration::from_millis(16)));
        }
        // Ответы Rust -> WebView доставляются на каждой итерации цикла, а не
        // только по RedrawRequested (иначе они застревали при свёрнутом окне).
        fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
            self.editor.process_messages();
            event_loop.set_control_flow(ControlFlow::WaitUntil(std::time::Instant::now() + std::time::Duration::from_millis(16)));
        }
        fn window_event(&mut self, event_loop: &ActiveEventLoop, id: WindowId, event: WindowEvent) {
            if self.editor.window.id() == id {
                if let WindowEvent::CloseRequested = event {
                    event_loop.exit();
                }
            }
        }
    }

    match EditorWindow::from_window(window, loader, ponies_dir) {
        Ok(editor) => {
            let mut app = EditorApp { editor };
            event_loop.run_app(&mut app).expect("editor loop");
        }
        Err(e) => {
            eprintln!("Failed to start editor: {}", e);
            std::process::exit(1);
        }
    }
}

#[cfg(windows)]
#[link(name = "winmm")]
extern "system" {
    fn timeBeginPeriod(period_ms: u32) -> u32;
}

fn main() {
    // Таймер Windows по умолчанию тикает ~15.6 мс, из-за чего FPS выше ~60
    // не достигался. Просим разрешение 1 мс на всё время работы процесса.
    #[cfg(windows)]
    unsafe {
        timeBeginPeriod(1);
    }
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|a| a == "--editor" || a == "-e") {
        run_editor_mode();
        return;
    }
    let event_loop = EventLoop::<app::UserEvent>::with_user_event().build().expect("event loop");
    let proxy = event_loop.create_proxy();
    let mut application = app::App::new(proxy);
    // --spawn "Twilight Sparkle,Applejack": сразу запустить этих пони.
    if let Some(pos) = args.iter().position(|a| a == "--spawn") {
        if let Some(list) = args.get(pos + 1) {
            application.autostart = list.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect();
        }
    }
    event_loop.run_app(&mut application).expect("run");
}
