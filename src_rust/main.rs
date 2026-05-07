// src_rust/main.rs
use std::num::NonZeroU32;
use std::sync::{Arc, Mutex};
use std::path::{Path, PathBuf};
use std::time::Instant;
use std::collections::HashSet;
use image::AnimationDecoder;
use winit::{
    event::WindowEvent,
    event_loop::{EventLoop, EventLoopProxy},
    window::{WindowAttributes, WindowLevel, WindowId},
    application::ApplicationHandler,
    dpi::LogicalSize,
};
use softbuffer::{Context, Surface};
use wry::WebViewBuilder;

mod loader;
mod monitor_manager;
mod settings;
use loader::{DesktopPoniesLoader, MovementType};
use monitor_manager::MonitorManager;
use settings::AppSettings;

#[derive(Debug, Clone)]
enum UserEvent {
    RequestRedraw,
    ReloadMonitors,
    ApplySettings {
        selected_monitors: Vec<String>,
    },
}

struct Pony {
    x: f32, y: f32,
    vx: f32, vy: f32,
    frames: Vec<Vec<u32>>,
    frame_count: u32,
    width: u32, height: u32,
    current_frame: u32,
    frame_timer: f32,
    frame_duration: f32,
    facing_right: bool,
    behavior_name: String,
    movement_type: MovementType,
    change_timer: f32,
}

fn load_pony_frames(pony_dir: &Path, sprite_name: &str) -> (Vec<Vec<u32>>, u32, u32, u32, f32) {
    if !pony_dir.exists() {
        return (vec![vec![0xFFFF0000u32; 32 * 32]], 1, 32, 32, 0.1);
    }

    let gif_path = pony_dir.join(sprite_name);
    if gif_path.exists() {
        return load_gif_file(&gif_path);
    }

    if let Ok(entries) = std::fs::read_dir(pony_dir) {
        for entry in entries.flatten() {
            if entry.path().extension().and_then(|e| e.to_str()) == Some("gif") {
                return load_gif_file(&entry.path());
            }
        }
    }

    (vec![vec![0xFFFF0000u32; 32*32]], 1, 32, 32, 0.1)
}

fn load_gif_file(path: &Path) -> (Vec<Vec<u32>>, u32, u32, u32, f32) {
    if let Ok(bytes) = std::fs::read(path) {
        if let Ok(decoder) = image::codecs::gif::GifDecoder::new(std::io::Cursor::new(&bytes)) {
            let frames: Vec<_> = decoder.into_frames().filter_map(|f: Result<image::Frame, _>| f.ok()).collect();
            if !frames.is_empty() {
                let w = frames[0].buffer().width();
                let h = frames[0].buffer().height();
                let fc = frames.len() as u32;
                let mut delays = Vec::new();
                let bgra: Vec<Vec<u32>> = frames.iter().map(|f: &image::Frame| {
                    let (d, _) = f.delay().numer_denom_ms();
                    delays.push(d as f32);
                    f.buffer().chunks(4).map(|p| {
                        ((p[3] as u32) << 24) | ((p[0] as u32) << 16) | ((p[1] as u32) << 8) | (p[2] as u32)
                    }).collect()
                }).collect();
                let avg = delays.iter().sum::<f32>() / delays.len() as f32 / 1000.0;
                return (bgra, fc, w, h, avg.max(0.05));
            }
        }
    }
    (vec![vec![0xFFFF0000; 32*32]], 1, 32, 32, 0.1)
}

fn build_html(loader: &DesktopPoniesLoader, monitors: &MonitorManager) -> String {
    let ponies: Vec<serde_json::Value> = loader.configs.iter().map(|c| {
        serde_json::json!({
            "name": c.name,
            "behaviors": c.behaviors.iter().map(|b| b.name.clone()).collect::<Vec<_>>(),
            "speaks_count": c.speaks.len()
        })
    }).collect();

    let monitors_data: Vec<serde_json::Value> = monitors.monitors.iter().map(|m| {
        serde_json::json!({
            "id": m.id,
            "name": m.name,
            "width": m.width,
            "height": m.height,
            "x": m.x,
            "y": m.y,
            "is_primary": m.is_primary,
            "scale_factor": m.scale_factor,
            "refresh_rate": m.refresh_rate_millihertz.map(|r| r as f32 / 1000.0)
        })
    }).collect();

    let ponies_json = serde_json::to_string(&ponies).unwrap_or_else(|_| "[]".to_string());
    let monitors_json = serde_json::to_string(&monitors_data).unwrap_or_else(|_| "[]".to_string());
    let selected_json = serde_json::to_string(&monitors.selected_ids).unwrap_or_else(|_| "[]".to_string());

    println!("[UI] Ponies: {} items", ponies.len());
    println!("[UI] Monitors: {} items, selected: {:?}", monitors_data.len(), monitors.selected_ids);

    let css = include_str!("../src-ui/style.css");
    let js = include_str!("../src-ui/app.js");
    let tpl = include_str!("../src-ui/index.html");

    // Данные ПЕРЕД скриптом
    let data_script = format!(
        "<script>window.PONIES_DATA={};window.MONITORS_DATA={};window.SELECTED_MONITORS={};</script>",
        ponies_json, monitors_json, selected_json
    );

    // Заменяем CSS
    let html = tpl.replace(
        "<link rel=\"stylesheet\" href=\"style.css\">",
        &format!("<style>{}</style>", css)
    );

    // Заменяем JS (конкатенация, не format!)
    let html = html.replace(
        "<script src=\"app.js\"></script>",
        &(data_script + "<script>" + js + "</script>")
    );

    println!("[UI] HTML size: {} bytes", html.len());
    html
}
struct PonyWindow {
    window: Arc<winit::window::Window>,
    surface: Surface<Arc<winit::window::Window>, Arc<winit::window::Window>>,
    monitor_id: String,
}

struct App {
    ponies: Vec<Pony>,
    pony_windows: Vec<PonyWindow>,
    ui_window: Option<Arc<winit::window::Window>>,
    _webview: Option<wry::WebView>,
    last_frame: Instant,
    spawn_queue: Arc<Mutex<Vec<String>>>,
    loader: DesktopPoniesLoader,
    proxy: EventLoopProxy<UserEvent>,
    monitor_manager: MonitorManager,
    settings: AppSettings,
    settings_path: PathBuf,
}

impl App {
    fn spawn_pony(&mut self, name: &str, _monitor_index: Option<usize>) {
        let config = match self.loader.configs.iter().find(|c| c.name == name) {
            Some(c) => c.clone(),
            None => {
                println!("[Spawn] Pony '{}' not found in configs", name);
                return;
            }
        };

        let available_behaviors: Vec<_> = config.behaviors.iter()
            .filter(|b| {
                (!b.sprite_right.is_empty() || !b.sprite_left.is_empty()) && !b.skip && b.probability > 0.0
            })
            .collect();

        if available_behaviors.is_empty() {
            println!("[Spawn] '{}' has no available behaviors", name);
            return;
        }

        let total_prob: f32 = available_behaviors.iter().map(|b| b.probability).sum();
        let mut rand_val = fastrand::f32() * total_prob;
        let mut chosen_behavior = available_behaviors[0];
        for behavior in &available_behaviors {
            rand_val -= behavior.probability;
            if rand_val <= 0.0 {
                chosen_behavior = behavior;
                break;
            }
        }

        let sprite_name = if fastrand::bool() {
            if !chosen_behavior.sprite_right.is_empty() { &chosen_behavior.sprite_right } else { &chosen_behavior.sprite_left }
        } else {
            if !chosen_behavior.sprite_left.is_empty() { &chosen_behavior.sprite_left } else { &chosen_behavior.sprite_right }
        };

        let pony_dir = Path::new("Ponies").join(name);
        let (frames, fc, w, h, delay) = load_pony_frames(&pony_dir, sprite_name);

        let speed = chosen_behavior.speed * 60.0;
        let angle = fastrand::f32() * std::f32::consts::TAU;

        let (screen_w, screen_h) = self.pony_windows.first()
            .and_then(|pw| {
                let size = pw.window.inner_size();
                Some((size.width as f32, size.height as f32))
            })
            .unwrap_or((1920.0, 1080.0));

        self.ponies.push(Pony {
            x: fastrand::f32() * (screen_w - 100.0) + 50.0,
            y: fastrand::f32() * (screen_h - 100.0) + 50.0,
            vx: angle.cos() * speed,
            vy: angle.sin() * speed,
            frames, frame_count: fc,
            width: w, height: h,
            current_frame: fastrand::u32(0..fc),
            frame_timer: fastrand::f32() * delay,
            frame_duration: delay,
            facing_right: true,
            behavior_name: chosen_behavior.name.clone(),
            movement_type: MovementType::parse(&chosen_behavior.movement),
            change_timer: fastrand::f32() * 3.0,
        });

        println!("[Spawn] '{}' spawned ({} total ponies)", name, self.ponies.len());
    }

    fn create_pony_windows(&mut self, event_loop: &winit::event_loop::ActiveEventLoop) {
        self.pony_windows.clear();

        let selected_ids: HashSet<String> = if self.monitor_manager.selected_ids.is_empty() {
            // Если ничего не выбрано, выбираем все мониторы
            self.monitor_manager.monitors.iter().map(|m| m.id.clone()).collect()
        } else {
            self.monitor_manager.selected_ids.iter().cloned().collect()
        };

        println!("[Windows] Creating windows for {} monitor(s): {:?}", selected_ids.len(), selected_ids);

        for monitor_info in &self.monitor_manager.monitors {
            if !selected_ids.contains(&monitor_info.id) {
                println!("[Windows] Skipping monitor '{}' (not selected)", monitor_info.name);
                continue;
            }

            let attrs = WindowAttributes::default()
                .with_decorations(false)
                .with_transparent(true)
                .with_inner_size(LogicalSize::new(monitor_info.width, monitor_info.height))
                .with_position(winit::dpi::PhysicalPosition::new(monitor_info.x, monitor_info.y));

            match event_loop.create_window(attrs) {
                Ok(window) => {
                    let pw = Arc::new(window);
                    pw.set_window_level(WindowLevel::AlwaysOnTop);
                    pw.set_cursor_hittest(false).ok();

                    match Context::new(pw.clone()) {
                        Ok(ctx) => {
                            let surface = Surface::new(&ctx, pw.clone()).unwrap();
                            self.pony_windows.push(PonyWindow {
                                window: pw,
                                surface,
                                monitor_id: monitor_info.id.clone(),
                            });
                            println!("[Windows] Created on '{}' {}x{}",
                                     monitor_info.name, monitor_info.width, monitor_info.height);
                        }
                        Err(e) => {
                            eprintln!("[Windows] Context error: {}", e);
                        }
                    }
                }
                Err(e) => {
                    eprintln!("[Windows] Window creation error: {}", e);
                }
            }
        }

        println!("[Windows] Total windows created: {}", self.pony_windows.len());
    }

    fn update_ponies(&mut self, dt: f32, screen_width: f32, screen_height: f32) {
        for p in &mut self.ponies {
            p.change_timer -= dt;

            if p.change_timer <= 0.0 {
                p.change_timer = fastrand::f32() * 3.0 + 1.0;
                match p.movement_type {
                    MovementType::None => { p.vx = 0.0; p.vy = 0.0; }
                    MovementType::All => {
                        let speed = (p.vx * p.vx + p.vy * p.vy).sqrt().max(30.0);
                        let angle = fastrand::f32() * std::f32::consts::TAU;
                        p.vx = angle.cos() * speed;
                        p.vy = angle.sin() * speed;
                    }
                    MovementType::HorizontalOnly => {
                        p.vx = p.vx.abs() * if fastrand::bool() { 1.0 } else { -1.0 };
                        p.vy = 0.0;
                    }
                    MovementType::VerticalOnly => {
                        p.vx = 0.0;
                        p.vy = p.vy.abs() * if fastrand::bool() { 1.0 } else { -1.0 };
                    }
                    MovementType::DiagonalOnly => {
                        let speed = p.vx.abs().max(30.0);
                        p.vx = speed * if fastrand::bool() { 1.0 } else { -1.0 };
                        p.vy = speed * if fastrand::bool() { 1.0 } else { -1.0 };
                    }
                    MovementType::DiagonalHorizontal => {
                        let speed = p.vx.abs().max(30.0);
                        p.vx = speed * if fastrand::bool() { 1.0 } else { -1.0 };
                        p.vy = speed * 0.5 * if fastrand::bool() { 1.0 } else { -1.0 };
                    }
                    MovementType::Sleep => { p.vx = 0.0; p.vy = 0.0; }
                    MovementType::Dragged => {}
                }
            }

            p.x += p.vx * dt;
            p.y += p.vy * dt;

            let margin = 10.0;
            let max_x = screen_width - p.width as f32 - margin;
            let max_y = screen_height - p.height as f32 - margin;

            if p.x < margin { p.x = margin; p.vx = p.vx.abs(); }
            if p.x > max_x { p.x = max_x; p.vx = -p.vx.abs(); }
            if p.y < margin { p.y = margin; p.vy = p.vy.abs(); }
            if p.y > max_y { p.y = max_y; p.vy = -p.vy.abs(); }

            p.facing_right = p.vx >= 0.0;

            p.frame_timer += dt;
            if p.frame_timer >= p.frame_duration {
                p.frame_timer -= p.frame_duration;
                p.current_frame = (p.current_frame + 1) % p.frame_count;
            }
        }
    }

    fn render_all_windows(&mut self) {
        let now = Instant::now();
        let dt = now.duration_since(self.last_frame).as_secs_f32().min(0.05);
        self.last_frame = now;

        let (default_w, default_h) = self.pony_windows.first()
            .and_then(|pw| {
                let size = pw.window.inner_size();
                Some((size.width as f32, size.height as f32))
            })
            .unwrap_or((1920.0, 1080.0));

        self.update_ponies(dt, default_w, default_h);

        // Разделяем ссылки для компилятора
        let ponies = &self.ponies;
        let pony_windows = &mut self.pony_windows;

        for pw in pony_windows.iter_mut() {
            let size = pw.window.inner_size();
            if let (Some(sw), Some(sh)) = (NonZeroU32::new(size.width), NonZeroU32::new(size.height)) {
                pw.surface.resize(sw, sh).unwrap();
                let mut buffer = pw.surface.buffer_mut().unwrap();
                let bw = sw.get() as usize;
                let bh = sh.get() as usize;

                buffer.fill(0x4400AA00);

                for p in ponies.iter() {
                    let frame = &p.frames[p.current_frame as usize];
                    let pw = p.width as usize;
                    for py in 0..p.height as usize {
                        let by = p.y as usize + py;
                        if by >= bh { continue; }
                        for px in 0..pw {
                            let bx = p.x as usize + px;
                            if bx >= bw { continue; }
                            let src_x = if !p.facing_right { pw - 1 - px } else { px };
                            let pixel = frame[py * pw + src_x];
                            if (pixel >> 24) > 0 {
                                buffer[by * bw + bx] = pixel;
                            }
                        }
                    }
                }

                buffer.present().unwrap();
            }
        }
    }
}

impl ApplicationHandler<UserEvent> for App {
    fn resumed(&mut self, event_loop: &winit::event_loop::ActiveEventLoop) {
        // Определяем мониторы при первом запуске
        if self.monitor_manager.monitors.is_empty() {
            self.monitor_manager.detect(event_loop);
            if self.monitor_manager.selected_ids.is_empty() {
                self.monitor_manager.selected_ids = self.monitor_manager.monitors.iter()
                    .map(|m| m.id.clone())
                    .collect();
            }
        }

        // Создаём UI-окно
        if self.ui_window.is_none() {
            let attrs = WindowAttributes::default()
                .with_title("Desktop Ponies")
                .with_inner_size(LogicalSize::new(420.0, 720.0));
            let ui_w = Arc::new(event_loop.create_window(attrs).unwrap());

            let q = self.spawn_queue.clone();
            let proxy = self.proxy.clone();
            let html_content = build_html(&self.loader, &self.monitor_manager);

            println!("[WebView] Creating with HTML size: {}", html_content.len());

            let wv = WebViewBuilder::new()
                .with_html(&html_content)
                .with_ipc_handler(move |request| {
                    let body = request.body();
                    println!("[IPC] Received: {}", body);

                    if let Some(n) = body.strip_prefix("spawn:") {
                        q.lock().unwrap().push(n.to_string());
                        let _ = proxy.send_event(UserEvent::RequestRedraw);
                    } else if body.starts_with("settings:") {
                        let settings_str = &body["settings:".len()..];
                        println!("[IPC] Settings: {}", settings_str);
                        if let Ok(settings_data) = serde_json::from_str::<serde_json::Value>(settings_str) {
                            if let Some(monitors) = settings_data["selected_monitors"].as_array() {
                                let ids: Vec<String> = monitors.iter()
                                    .filter_map(|v| v.as_str().map(String::from))
                                    .collect();
                                println!("[IPC] New monitor selection: {:?}", ids);
                                let _ = proxy.send_event(UserEvent::ApplySettings {
                                    selected_monitors: ids,
                                });
                            }
                        }
                    } else if body == "reload_monitors" {
                        println!("[IPC] Reload monitors");
                        let _ = proxy.send_event(UserEvent::ReloadMonitors);
                    }
                })
                .build(&*ui_w)
                .unwrap();

            ui_w.set_visible(true);
            self.ui_window = Some(ui_w);
            self._webview = Some(wv);

            println!("[WebView] Created successfully");
        }

        // Создаём окна для мониторов
        if self.pony_windows.is_empty() {
            println!("[App] Creating pony windows...");
            self.create_pony_windows(event_loop);
        }
    }

    fn user_event(&mut self, event_loop: &winit::event_loop::ActiveEventLoop, event: UserEvent) {
        match event {
            UserEvent::RequestRedraw => {
                for pw in &self.pony_windows {
                    pw.window.request_redraw();
                }
            }
            UserEvent::ReloadMonitors => {
                println!("[Event] Reloading monitors...");
                self.monitor_manager.detect(event_loop);
                if self.monitor_manager.selected_ids.is_empty() {
                    self.monitor_manager.selected_ids = self.monitor_manager.monitors.iter()
                        .map(|m| m.id.clone())
                        .collect();
                }
                self.create_pony_windows(event_loop);
            }
            UserEvent::ApplySettings { selected_monitors } => {
                println!("[Event] Applying monitor settings: {:?}", selected_monitors);

                // Обновляем настройки
                self.settings.selected_monitors = selected_monitors.iter().cloned().collect();
                self.monitor_manager.selected_ids = selected_monitors.clone();

                // Сохраняем в файл
                self.settings.save(&self.settings_path);

                // Пересоздаём окна
                self.create_pony_windows(event_loop);

                // Если все мониторы отключены - очищаем пони
                if self.pony_windows.is_empty() {
                    println!("[Event] No monitors selected, clearing ponies");
                    self.ponies.clear();
                }

                println!("[Event] Settings applied, {} windows active", self.pony_windows.len());
            }
        }
    }

    fn window_event(&mut self, event_loop: &winit::event_loop::ActiveEventLoop, window_id: WindowId, event: WindowEvent) {
        let ui_id = self.ui_window.as_ref().map(|w| w.id());

        match event {
            WindowEvent::CloseRequested if Some(window_id) == ui_id => {
                println!("[App] Closing, saving settings...");
                self.settings.save(&self.settings_path);
                event_loop.exit();
            }
            WindowEvent::RedrawRequested => {
                // Обрабатываем очередь спавна
                let to_spawn: Vec<String> = self.spawn_queue.lock().unwrap().drain(..).collect();
                for name in to_spawn {
                    self.spawn_pony(&name, None);
                }

                self.render_all_windows();

                // Запрашиваем перерисовку со всех окон
                for pw in &self.pony_windows {
                    pw.window.request_redraw();
                }
            }
            _ => {}
        }
    }
}

fn main() {
    let spawn_q = Arc::new(Mutex::new(Vec::<String>::new()));

    let mut loader = DesktopPoniesLoader::new(".");
    if let Err(e) = loader.load_all() {
        eprintln!("Warning: Could not load ponies: {}", e);
    }

    let settings_path = std::env::current_exe()
        .unwrap_or_else(|_| PathBuf::from("."))
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .join("desktop_ponies_settings.json");

    let settings = AppSettings::load(&settings_path);

    // Инициализируем MonitorManager с сохранёнными настройками
    let mut monitor_manager = MonitorManager::new();
    monitor_manager.selected_ids = settings.selected_monitors.iter().cloned().collect();

    println!("[Main] Settings loaded, selected monitors: {:?}", monitor_manager.selected_ids);
    println!("[Main] Settings path: {:?}", settings_path);

    let el = EventLoop::<UserEvent>::with_user_event().build().unwrap();
    let proxy = el.create_proxy();

    el.run_app(&mut App {
        ponies: Vec::new(),
        pony_windows: Vec::new(),
        ui_window: None,
        _webview: None,
        last_frame: Instant::now(),
        spawn_queue: spawn_q,
        loader,
        proxy,
        monitor_manager,
        settings,
        settings_path,
    }).unwrap();
}