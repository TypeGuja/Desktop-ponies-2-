// src_rust/main.rs
use std::num::NonZeroU32;
use std::sync::{Arc, Mutex};
use std::path::PathBuf;
use std::time::Instant;
use std::collections::HashSet;
use winit::{
    event::{WindowEvent, ElementState, MouseButton},
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
mod performance;
use loader::{DesktopPoniesLoader, MovementType, Behavior};
use monitor_manager::MonitorManager;
use settings::AppSettings;
use performance::PerformanceMonitor;

#[derive(Debug, Clone)]
enum UserEvent {
    RequestRedraw,
    ReloadMonitors,
    ApplySettings { selected_monitors: Vec<String> },
    SetFPS(u32),
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
    config_name: String,
    current_behavior: String,
    available_behaviors: Vec<Behavior>,
    movement_type: MovementType,
    behavior_timer: f32,
    grabbed: bool,
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
    mouse_x: f32,
    mouse_y: f32,
    mouse_down: bool,
    grabbed_pony: Option<usize>,
    perf: PerformanceMonitor,
    frame_counter: u64,
    fps_limit: u32,
    frame_timer: Instant,
}

fn build_html(loader: &DesktopPoniesLoader, monitors: &MonitorManager, fps_limit: u32) -> String {
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

    let css = include_str!("../src-ui/style.css");
    let js = include_str!("../src-ui/app.js");
    let tpl = include_str!("../src-ui/index.html");

    let data_script = format!(
        "<script>window.PONIES_DATA={};window.MONITORS_DATA={};window.SELECTED_MONITORS={};window.FPS_LIMIT={};</script>",
        ponies_json, monitors_json, selected_json, fps_limit
    );

    let html = tpl.replace(
        "<link rel=\"stylesheet\" href=\"style.css\">",
        &format!("<style>{}</style>", css)
    );
    let html = html.replace(
        "<script src=\"app.js\"></script>",
        &(data_script + "<script>" + js + "</script>")
    );

    html
}

impl App {
    fn spawn_pony(&mut self, name: &str, _monitor_index: Option<usize>) {
        while self.ponies.len() >= 50 {
            self.ponies.remove(0);
        }

        let config = match self.loader.get_config(name) {
            Some(c) => c.clone(),
            None => { return; }
        };

        let available_behaviors: Vec<Behavior> = config.behaviors.iter()
            .filter(|b| (!b.sprite_right.is_empty() || !b.sprite_left.is_empty()) && !b.skip)
            .cloned()
            .collect();

        if available_behaviors.is_empty() { return; }

        let first_behavior = available_behaviors.iter()
            .find(|b| {
                let n = b.name.to_lowercase();
                n.contains("stand") || n.contains("idle")
            })
            .unwrap_or(&available_behaviors[0])
            .clone();

        let (sprite_name, facing_right) = if !first_behavior.sprite_right.is_empty() {
            (first_behavior.sprite_right.clone(), true)
        } else {
            (first_behavior.sprite_left.clone(), false)
        };

        let (frames, fc, w, h, delay) = self.loader.load_pony_frames(name, &sprite_name);
        let speed = first_behavior.speed * 60.0;
        let angle = fastrand::f32() * std::f32::consts::TAU;

        let (screen_w, screen_h) = self.pony_windows.first()
            .and_then(|pw| {
                let size = pw.window.inner_size();
                Some((size.width as f32, size.height as f32))
            })
            .unwrap_or((1920.0, 1080.0));

        self.ponies.push(Pony {
            x: fastrand::f32() * (screen_w - 200.0) + 100.0,
            y: fastrand::f32() * (screen_h - 200.0) + 100.0,
            vx: angle.cos() * speed,
            vy: angle.sin() * speed,
            frames,
            frame_count: fc,
            width: w,
            height: h,
            current_frame: 0,
            frame_timer: 0.0,
            frame_duration: delay,
            facing_right,
            config_name: name.to_string(),
            current_behavior: first_behavior.name.clone(),
            available_behaviors,
            movement_type: MovementType::parse(&first_behavior.movement),
            behavior_timer: first_behavior.min_duration + fastrand::f32() * (first_behavior.max_duration - first_behavior.min_duration),
            grabbed: false,
        });
    }

    fn create_pony_windows(&mut self, event_loop: &winit::event_loop::ActiveEventLoop) {
        self.pony_windows.clear();

        let selected_ids: HashSet<String> = if self.monitor_manager.selected_ids.is_empty() {
            self.monitor_manager.monitors.iter().map(|m| m.id.clone()).collect()
        } else {
            self.monitor_manager.selected_ids.iter().cloned().collect()
        };

        for monitor_info in &self.monitor_manager.monitors {
            if !selected_ids.contains(&monitor_info.id) { continue; }

            let attrs = WindowAttributes::default()
                .with_decorations(false)
                .with_transparent(true)
                .with_inner_size(LogicalSize::new(monitor_info.width, monitor_info.height))
                .with_position(winit::dpi::PhysicalPosition::new(monitor_info.x, monitor_info.y));

            if let Ok(window) = event_loop.create_window(attrs) {
                let pw = Arc::new(window);
                pw.set_window_level(WindowLevel::AlwaysOnTop);
                pw.set_cursor_hittest(false).ok();

                if let Ok(ctx) = Context::new(pw.clone()) {
                    if let Ok(surface) = Surface::new(&ctx, pw.clone()) {
                        self.pony_windows.push(PonyWindow {
                            window: pw,
                            surface,
                            monitor_id: monitor_info.id.clone(),
                        });
                    }
                }
            }
        }
    }

    fn render_all_windows(&mut self) {
        // Ограничение FPS
        let frame_duration = std::time::Duration::from_secs_f64(1.0 / self.fps_limit as f64);
        if self.frame_timer.elapsed() < frame_duration {
            return;
        }
        self.frame_timer = Instant::now();

        let now = Instant::now();
        let dt = now.duration_since(self.last_frame).as_secs_f32().min(0.05);
        self.last_frame = now;

        let (default_w, default_h) = self.pony_windows.first()
            .and_then(|pw| {
                let size = pw.window.inner_size();
                Some((size.width as f32, size.height as f32))
            })
            .unwrap_or((1920.0, 1080.0));

        update_ponies(
            &mut self.ponies,
            &mut self.loader,
            dt,
            default_w,
            default_h,
            self.mouse_x,
            self.mouse_y,
            self.mouse_down,
            &self.pony_windows,
            &mut self.grabbed_pony,
        );

        let ponies = &self.ponies;
        let pony_windows = &mut self.pony_windows;

        for pw in pony_windows.iter_mut() {
            let size = pw.window.inner_size();
            if let (Some(sw), Some(sh)) = (NonZeroU32::new(size.width), NonZeroU32::new(size.height)) {
                pw.surface.resize(sw, sh).unwrap();
                let mut buffer = pw.surface.buffer_mut().unwrap();
                let bw = sw.get() as usize;
                let bh = sh.get() as usize;
                buffer.fill(0x00000000);

                for p in ponies.iter() {
                    if p.current_frame as usize >= p.frames.len() { continue; }

                    let frame = &p.frames[p.current_frame as usize];
                    let pw = p.width as usize;

                    let x0 = p.x.max(0.0) as usize;
                    let y0 = p.y.max(0.0) as usize;
                    let x1 = ((p.x + p.width as f32).min(bw as f32)).max(0.0) as usize;
                    let y1 = ((p.y + p.height as f32).min(bh as f32)).max(0.0) as usize;

                    for by in y0..y1 {
                        let py = by - p.y as usize;
                        let row_offset = by * bw;
                        let frame_row = py * pw;

                        for bx in x0..x1 {
                            let px = bx - p.x as usize;
                            let src_x = if !p.facing_right { pw - 1 - px } else { px };
                            if frame_row + src_x < frame.len() {
                                let pixel = frame[frame_row + src_x];
                                if (pixel >> 24) > 0 {
                                    buffer[row_offset + bx] = pixel;
                                }
                            }
                        }
                    }
                }
                buffer.present().unwrap();
            }
        }

        self.frame_counter += 1;
        self.perf.update(self.ponies.len(), 0);
        if self.frame_counter % 60 == 0 {
            println!("[Stats] {}", self.perf.stats_string());
        }
    }
}

fn change_pony_behavior(pony: &mut Pony, loader: &mut DesktopPoniesLoader) {
    if pony.available_behaviors.is_empty() { return; }

    let total_prob: f32 = pony.available_behaviors.iter().map(|b| b.probability).sum();
    if total_prob <= 0.0 { return; }

    let mut rand_val = fastrand::f32() * total_prob;
    let mut chosen = &pony.available_behaviors[0];
    for behavior in &pony.available_behaviors {
        rand_val -= behavior.probability;
        if rand_val <= 0.0 {
            chosen = behavior;
            break;
        }
    }

    let sprite_name = if !chosen.sprite_right.is_empty() {
        &chosen.sprite_right
    } else {
        &chosen.sprite_left
    };

    let (frames, fc, w, h, delay) = loader.load_pony_frames(&pony.config_name, sprite_name);

    pony.frames = frames;
    pony.frame_count = fc;
    pony.width = w;
    pony.height = h;
    pony.frame_duration = delay;
    pony.current_frame = 0;
    pony.frame_timer = 0.0;
    pony.current_behavior = chosen.name.clone();
    pony.movement_type = MovementType::parse(&chosen.movement);
    pony.behavior_timer = chosen.min_duration + fastrand::f32() * (chosen.max_duration - chosen.min_duration);

    let speed = match pony.movement_type {
        MovementType::None | MovementType::Sleep => 0.0,
        _ => chosen.speed * 60.0,
    };

    if speed > 0.0 {
        let angle = fastrand::f32() * std::f32::consts::TAU;
        pony.vx = angle.cos() * speed;
        pony.vy = angle.sin() * speed;
    } else {
        pony.vx = 0.0;
        pony.vy = 0.0;
    }
}

fn update_ponies(
    ponies: &mut Vec<Pony>,
    loader: &mut DesktopPoniesLoader,
    dt: f32,
    screen_width: f32,
    screen_height: f32,
    mouse_x: f32,
    mouse_y: f32,
    mouse_down: bool,
    pony_windows: &Vec<PonyWindow>,
    grabbed_pony: &mut Option<usize>,
) {
    for i in 0..ponies.len() {
        let p = &mut ponies[i];

        if p.grabbed {
            if mouse_down {
                if let Some(pw) = pony_windows.first() {
                    if let Ok(pos) = pw.window.outer_position() {
                        p.x = (mouse_x - pos.x as f32 - p.width as f32 / 2.0)
                            .max(0.0)
                            .min(screen_width - p.width as f32);
                        p.y = (mouse_y - pos.y as f32 - p.height as f32 / 2.0)
                            .max(0.0)
                            .min(screen_height - p.height as f32);
                    }
                }
                p.vx = 0.0;
                p.vy = 0.0;
            } else {
                p.grabbed = false;
                p.movement_type = MovementType::None;
                p.behavior_timer = 0.0;
                *grabbed_pony = None;
            }

            p.frame_timer += dt;
            while p.frame_timer >= p.frame_duration {
                p.frame_timer -= p.frame_duration;
                p.current_frame = (p.current_frame + 1) % p.frame_count;
            }
            continue;
        }

        p.behavior_timer -= dt;
        if p.behavior_timer <= 0.0 {
            change_pony_behavior(p, loader);
        }

        match p.movement_type {
            MovementType::None | MovementType::Sleep => {
                p.vx = 0.0;
                p.vy = 0.0;
            }
            MovementType::HorizontalOnly => { p.vy = 0.0; }
            MovementType::VerticalOnly => { p.vx = 0.0; }
            _ => {}
        }

        p.x += p.vx * dt;
        p.y += p.vy * dt;

        p.x = p.x.max(0.0).min(screen_width - p.width as f32);
        p.y = p.y.max(0.0).min(screen_height - p.height as f32);

        let margin = 50.0;
        if p.x < margin { p.vx = p.vx.abs(); }
        if p.x > screen_width - p.width as f32 - margin { p.vx = -p.vx.abs(); }
        if p.y < margin { p.vy = p.vy.abs(); }
        if p.y > screen_height - p.height as f32 - margin { p.vy = -p.vy.abs(); }

        if p.vx.abs() > 1.0 { p.facing_right = p.vx > 0.0; }

        p.frame_timer += dt;
        while p.frame_timer >= p.frame_duration {
            p.frame_timer -= p.frame_duration;
            p.current_frame = (p.current_frame + 1) % p.frame_count;
        }
    }
}

impl ApplicationHandler<UserEvent> for App {
    fn resumed(&mut self, event_loop: &winit::event_loop::ActiveEventLoop) {
        if self.monitor_manager.monitors.is_empty() {
            self.monitor_manager.detect(event_loop);
            if self.monitor_manager.selected_ids.is_empty() {
                self.monitor_manager.selected_ids = self.monitor_manager.monitors.iter()
                    .map(|m| m.id.clone())
                    .collect();
            }
        }

        if self.ui_window.is_none() {
            let attrs = WindowAttributes::default()
                .with_title("Desktop Ponies")
                .with_inner_size(LogicalSize::new(420.0, 720.0));
            let ui_w = Arc::new(event_loop.create_window(attrs).unwrap());

            let q = self.spawn_queue.clone();
            let proxy = self.proxy.clone();
            let html_content = build_html(&self.loader, &self.monitor_manager, self.fps_limit);

            let wv = WebViewBuilder::new()
                .with_html(&html_content)
                .with_ipc_handler(move |request| {
                    let body = request.body();
                    if let Some(n) = body.strip_prefix("spawn:") {
                        q.lock().unwrap().push(n.to_string());
                        let _ = proxy.send_event(UserEvent::RequestRedraw);
                    } else if body.starts_with("settings:") {
                        let settings_str = &body["settings:".len()..];
                        if let Ok(data) = serde_json::from_str::<serde_json::Value>(settings_str) {
                            if let Some(monitors) = data["selected_monitors"].as_array() {
                                let ids: Vec<String> = monitors.iter()
                                    .filter_map(|v| v.as_str().map(String::from))
                                    .collect();
                                let _ = proxy.send_event(UserEvent::ApplySettings { selected_monitors: ids });
                            }
                        }
                    } else if body == "reload_monitors" {
                        let _ = proxy.send_event(UserEvent::ReloadMonitors);
                    } else if body.starts_with("fps:") {
                        let fps_str = &body["fps:".len()..];
                        if let Ok(fps) = fps_str.parse::<u32>() {
                            let _ = proxy.send_event(UserEvent::SetFPS(fps));
                        }
                    }
                })
                .build(&*ui_w)
                .unwrap();

            ui_w.set_visible(true);
            self.ui_window = Some(ui_w);
            self._webview = Some(wv);
        }

        if self.pony_windows.is_empty() {
            self.create_pony_windows(event_loop);
        }
    }

    fn window_event(&mut self, event_loop: &winit::event_loop::ActiveEventLoop, window_id: WindowId, event: WindowEvent) {
        let ui_id = self.ui_window.as_ref().map(|w| w.id());

        match event {
            WindowEvent::CloseRequested if Some(window_id) == ui_id => {
                self.settings.save(&self.settings_path);
                event_loop.exit();
            }
            WindowEvent::CursorMoved { position, .. } if Some(window_id) == ui_id => {
                self.mouse_x = position.x as f32;
                self.mouse_y = position.y as f32;
            }
            WindowEvent::MouseInput { state, button, .. } if button == MouseButton::Left && Some(window_id) == ui_id => {
                if state == ElementState::Pressed {
                    self.mouse_down = true;

                    for pw in &self.pony_windows {
                        if let Ok(win_pos) = pw.window.outer_position() {
                            if let Some(ui_w) = &self.ui_window {
                                if let Ok(ui_pos) = ui_w.outer_position() {
                                    let global_x = ui_pos.x as f32 + self.mouse_x;
                                    let global_y = ui_pos.y as f32 + self.mouse_y;
                                    let local_x = global_x - win_pos.x as f32;
                                    let local_y = global_y - win_pos.y as f32;

                                    let mut grabbed_idx = None;
                                    for i in (0..self.ponies.len()).rev() {
                                        let p = &self.ponies[i];
                                        if local_x >= p.x && local_x <= p.x + p.width as f32 &&
                                            local_y >= p.y && local_y <= p.y + p.height as f32 {
                                            grabbed_idx = Some(i);
                                            break;
                                        }
                                    }

                                    if let Some(i) = grabbed_idx {
                                        let p = &self.ponies[i];
                                        let pony_name = p.config_name.clone();

                                        let drag_data = if let Some(config) = self.loader.get_config(&pony_name) {
                                            if let Some(drag) = config.behaviors.iter().find(|b| b.name == "drag") {
                                                let sprite_name = if !drag.sprite_right.is_empty() {
                                                    drag.sprite_right.clone()
                                                } else {
                                                    drag.sprite_left.clone()
                                                };
                                                Some((sprite_name.clone(), self.loader.load_pony_frames(&pony_name, &sprite_name)))
                                            } else {
                                                None
                                            }
                                        } else {
                                            None
                                        };

                                        let p = &mut self.ponies[i];
                                        if let Some((_, (frames, fc, w, h, delay))) = drag_data {
                                            p.frames = frames;
                                            p.frame_count = fc;
                                            p.width = w;
                                            p.height = h;
                                            p.frame_duration = delay;
                                            p.current_frame = 0;
                                            p.frame_timer = 0.0;
                                            p.current_behavior = "drag".to_string();
                                        }
                                        p.grabbed = true;
                                        p.movement_type = MovementType::Dragged;
                                        self.grabbed_pony = Some(i);
                                    }
                                }
                            }
                        }
                    }
                } else {
                    self.mouse_down = false;
                }
            }
            WindowEvent::RedrawRequested => {
                let to_spawn: Vec<String> = self.spawn_queue.lock().unwrap().drain(..).collect();
                for name in to_spawn {
                    self.spawn_pony(&name, None);
                }

                self.render_all_windows();

                for pw in &self.pony_windows {
                    pw.window.request_redraw();
                }
            }
            _ => {}
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
                self.monitor_manager.detect(event_loop);
                if self.monitor_manager.selected_ids.is_empty() {
                    self.monitor_manager.selected_ids = self.monitor_manager.monitors.iter()
                        .map(|m| m.id.clone())
                        .collect();
                }
                self.create_pony_windows(event_loop);
            }
            UserEvent::ApplySettings { selected_monitors } => {
                self.settings.selected_monitors = selected_monitors.iter().cloned().collect();
                self.monitor_manager.selected_ids = selected_monitors;
                self.settings.save(&self.settings_path);
                self.create_pony_windows(event_loop);
                if self.pony_windows.is_empty() {
                    self.ponies.clear();
                }
            }
            UserEvent::SetFPS(fps) => {
                self.fps_limit = fps.clamp(10, 120);
                self.settings.fps_limit = self.fps_limit;
                self.settings.save(&self.settings_path);
                println!("[FPS] Set to {}", self.fps_limit);
            }
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
        .unwrap_or_else(|| std::path::Path::new("."))
        .join("desktop_ponies_settings.json");

    let settings = AppSettings::load(&settings_path);

    let mut monitor_manager = MonitorManager::new();
    monitor_manager.selected_ids = settings.selected_monitors.iter().cloned().collect();

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
        mouse_x: 0.0,
        mouse_y: 0.0,
        mouse_down: false,
        grabbed_pony: None,
        perf: PerformanceMonitor::new(),
        frame_counter: 0,
        fps_limit: 60,
        frame_timer: Instant::now(),
    }).unwrap();
}