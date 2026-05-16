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
    dpi::{LogicalSize, PhysicalPosition, PhysicalSize},
};
use softbuffer::{Context, Surface};
use wry::WebViewBuilder;

mod loader;
mod monitor_manager;
mod settings;
mod performance;
mod context_menu;
use loader::{DesktopPoniesLoader, MovementType, Behavior};
use monitor_manager::MonitorManager;
use settings::AppSettings;
use performance::PerformanceMonitor;
use context_menu::{ContextMenu, PonyAction};

// ==================== ТИПЫ ДАННЫХ ====================

#[derive(Debug, Clone)]
enum UserEvent {
    RequestRedraw,
    ReloadMonitors,
    ApplySettings { selected_monitors: Vec<String> },
    SetFPS(u32),
    UpdateInteractionWindows,
}

#[derive(Clone, Debug)]
enum InteractionState {
    Booped { timer: f32 },
    Fed { timer: f32, original_speed_mult: f32 },
    Petted { timer: f32 },
    Sleeping,
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
    interaction_state: Option<InteractionState>,
    original_frame_duration: Option<f32>,
}

struct InteractionWindow {
    window: Arc<winit::window::Window>,
    surface: Surface<Arc<winit::window::Window>, Arc<winit::window::Window>>,
    pony_index: usize,
}

struct App {
    ponies: Vec<Pony>,
    main_window: Option<Arc<winit::window::Window>>,
    main_surface: Option<Surface<Arc<winit::window::Window>, Arc<winit::window::Window>>>,
    interaction_windows: Vec<InteractionWindow>,
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
    right_mouse_down: bool,
    grabbed_pony: Option<usize>,
    context_menu: ContextMenu,
    perf: PerformanceMonitor,
    frame_counter: u64,
    fps_limit: u32,
    frame_timer: Instant,
    debug_hitboxes: bool,
}

// ==================== HTML BUILDER ====================

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

// ==================== APP IMPL ====================

impl App {
    fn spawn_pony(&mut self, name: &str, event_loop: &winit::event_loop::ActiveEventLoop) {
        while self.ponies.len() >= 50 {
            self.remove_pony(0, event_loop);
        }

        let config = match self.loader.get_config(name) {
            Some(c) => c.clone(),
            None => { return; }
        };

        let available_behaviors: Vec<Behavior> = config.behaviors.iter()
            .filter(|b| !b.skip && (!b.sprite_right.is_empty() || !b.sprite_left.is_empty()))
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

        let (screen_w, screen_h) = self.main_window.as_ref()
            .map(|w| {
                let size = w.inner_size();
                (size.width as f32, size.height as f32)
            })
            .unwrap_or((1920.0, 1080.0));

        let pony_index = self.ponies.len();

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
            interaction_state: None,
            original_frame_duration: None,
        });

        // Создаём окно взаимодействия для этого пони
        self.create_interaction_window(pony_index, event_loop);

        // Сразу обновляем позицию и показываем окно
        self.update_interaction_windows();

        println!("[Spawn] Created pony '{}' (#{}) at ({:.0},{:.0}) with interaction window",
                 name, pony_index, self.ponies[pony_index].x, self.ponies[pony_index].y);
    }

    fn create_interaction_window(&mut self, pony_index: usize, event_loop: &winit::event_loop::ActiveEventLoop) {
        let pony = &self.ponies[pony_index];
        let padding = 6.0;
        let window_w = (pony.width as f64 + padding * 2.0).max(50.0);
        let window_h = (pony.height as f64 + padding * 2.0).max(50.0);

        println!("[Interaction] Creating window for pony #{}: {}x{}", pony_index, window_w, window_h);

        let attrs = WindowAttributes::default()
            .with_title(format!("Pony Interaction {}", pony_index))
            .with_decorations(false)
            .with_transparent(true)
            .with_visible(false)
            .with_inner_size(LogicalSize::new(window_w, window_h))
            .with_window_level(WindowLevel::AlwaysOnTop);

        if let Ok(window) = event_loop.create_window(attrs) {
            let pw = Arc::new(window);
            // ВАЖНО: окно НЕ прозрачно для кликов
            pw.set_cursor_hittest(true).ok();

            if let Ok(ctx) = Context::new(pw.clone()) {
                if let Ok(mut surface) = Surface::new(&ctx, pw.clone()) {
                    // Рисуем полупрозрачный синий фон
                    if let (Some(w), Some(h)) = (
                        NonZeroU32::new(window_w as u32),
                        NonZeroU32::new(window_h as u32)
                    ) {
                        surface.resize(w, h).unwrap();
                        let mut buffer = surface.buffer_mut().unwrap();
                        // Полупрозрачный синий (альфа 128)
                        let blue_color = 0x00000000;
                        buffer.fill(blue_color);
                        buffer.present().unwrap();
                    }

                    self.interaction_windows.push(InteractionWindow {
                        window: pw.clone(),
                        surface,
                        pony_index,
                    });

                    // ВАЖНО: Показываем окно сразу после создания
                    pw.set_visible(true);

                    println!("[Interaction] Created and SHOWN window for pony #{} ({}x{})",
                             pony_index, window_w, window_h);
                }
            }
        } else {
            eprintln!("[Error] Failed to create interaction window for pony #{}", pony_index);
        }
    }

    fn remove_pony(&mut self, index: usize, _event_loop: &winit::event_loop::ActiveEventLoop) {
        if index < self.ponies.len() {
            println!("[Remove] Removing pony #{}", index);

            // Скрываем и удаляем окно взаимодействия
            if let Some(iw_idx) = self.interaction_windows.iter().position(|iw| iw.pony_index == index) {
                self.interaction_windows[iw_idx].window.set_visible(false);
                println!("[Remove] Hidden interaction window for pony #{}", index);
            }

            // Удаляем окно
            self.interaction_windows.retain(|iw| iw.pony_index != index);

            // Обновляем индексы в оставшихся окнах
            for iw in &mut self.interaction_windows {
                if iw.pony_index > index {
                    iw.pony_index -= 1;
                }
            }

            self.ponies.remove(index);

            // Обновляем grabbed_pony
            if self.grabbed_pony == Some(index) {
                self.grabbed_pony = None;
            } else if let Some(g) = self.grabbed_pony {
                if g > index {
                    self.grabbed_pony = Some(g - 1);
                }
            }

            println!("[Remove] Pony #{} removed successfully", index);
        }
    }

    fn update_interaction_windows(&mut self) {
        if let Some(main_window) = &self.main_window {
            if let Ok(main_pos) = main_window.outer_position() {
                let padding = 6.0;

                for iw in &self.interaction_windows {
                    if iw.pony_index < self.ponies.len() {
                        let pony = &self.ponies[iw.pony_index];

                        let x = main_pos.x + (pony.x - padding) as i32;
                        let y = main_pos.y + (pony.y - padding) as i32;
                        let w = ((pony.width as f32 + padding * 2.0) as u32).max(50);
                        let h = ((pony.height as f32 + padding * 2.0) as u32).max(50);

                        // Позиционируем окно
                        let _ = iw.window.set_outer_position(PhysicalPosition::new(x.max(0), y.max(0)));
                        let _ = iw.window.request_inner_size(PhysicalSize::new(w, h));

                        // Показываем/скрываем
                        let is_sleeping = matches!(pony.interaction_state, Some(InteractionState::Sleeping));
                        let should_show = !is_sleeping;

                        let is_visible = iw.window.is_visible().unwrap_or(false);
                        if should_show != is_visible {
                            iw.window.set_visible(should_show);
                        }
                    }
                }
            }
        }
    }

    fn render_interaction_windows(&mut self) {
        let padding = 6.0;

        for iw in self.interaction_windows.iter_mut() {
            if iw.pony_index < self.ponies.len() {
                let pony = &self.ponies[iw.pony_index];
                let window_w = ((pony.width as f32 + padding * 2.0) as u32).max(50);
                let window_h = ((pony.height as f32 + padding * 2.0) as u32).max(50);

                if let (Some(w), Some(h)) = (
                    NonZeroU32::new(window_w),
                    NonZeroU32::new(window_h)
                ) {
                    if let Err(e) = iw.surface.resize(w, h) {
                        eprintln!("[Error] Failed to resize surface for window: {:?}", e);
                        continue;
                    }

                    if let Ok(mut buffer) = iw.surface.buffer_mut() {
                        // Полупрозрачный синий фон
                        let blue_color = 0x00000000;
                        buffer.fill(blue_color);

                        // Дебаг: рисуем рамку
                        if self.debug_hitboxes {
                            let bw = w.get() as usize;
                            let bh = h.get() as usize;
                            let border_color = 0xFFFF0000;

                            for x in 0..bw {
                                if bh > 0 { buffer[x] = border_color; }
                                if bh > 1 { buffer[(bh-1) * bw + x] = border_color; }
                            }
                            for y in 0..bh {
                                if bw > 0 { buffer[y * bw] = border_color; }
                                if bw > 1 { buffer[y * bw + (bw-1)] = border_color; }
                            }
                        }

                        buffer.present().unwrap();
                    }
                }
            }
        }
    }

    fn render_context_menu(&mut self) {
        if !self.context_menu.visible {
            return;
        }

        // Рисуем меню поверх главного окна
        if let Some(surface) = &mut self.main_surface {
            if let Some(window) = &self.main_window {
                let size = window.inner_size();
                if let (Some(sw), Some(sh)) = (NonZeroU32::new(size.width), NonZeroU32::new(size.height)) {
                    if let Ok(mut buffer) = surface.buffer_mut() {
                        let bw = sw.get() as usize;
                        let bh = sh.get() as usize;

                        let menu_x = self.context_menu.x as usize;
                        let menu_y = self.context_menu.y as usize;
                        let menu_width = 180;
                        let item_height = 28;
                        let padding = 4;

                        let bg_color = 0x00000000; // Тёмный фон
                        let border_color = 0x00000000; // Синяя рамка
                        let hover_color = 0x00000000; // Подсветка

                        let total_height = self.context_menu.items.len() * item_height + padding * 2;

                        // Проверяем границы
                        if menu_x + menu_width > bw || menu_y + total_height > bh {
                            return; // Меню выходит за границы окна
                        }

                        // Фон меню с рамкой
                        for y in menu_y..(menu_y + total_height).min(bh) {
                            for x in menu_x..(menu_x + menu_width).min(bw) {
                                if x == menu_x || x == menu_x + menu_width - 1 ||
                                    y == menu_y || y == menu_y + total_height - 1 {
                                    buffer[y * bw + x] = border_color;
                                } else {
                                    buffer[y * bw + x] = bg_color;
                                }
                            }
                        }

                        // Определяем hover-элемент
                        let hover_idx = self.context_menu.hit_test(self.mouse_x, self.mouse_y);

                        // Рисуем пункты меню с подсветкой и разделителями
                        for i in 0..self.context_menu.items.len() {
                            let item_y = menu_y + padding + i * item_height;
                            let item = &self.context_menu.items[i];

                            // Фон пункта
                            let item_bg = if Some(i) == hover_idx && item.enabled {
                                hover_color
                            } else if !item.enabled {
                                0xCC555555 // Серый для недоступных
                            } else {
                                bg_color
                            };

                            for y in item_y..(item_y + item_height).min(bh) {
                                let row_start = y * bw;
                                for x in (menu_x + 1)..(menu_x + menu_width - 1).min(bw) {
                                    buffer[row_start + x] = item_bg;
                                }
                            }

                            // Разделитель между пунктами
                            if i < self.context_menu.items.len() - 1 {
                                let sep_y = item_y + item_height - 1;
                                if sep_y < bh {
                                    let row_start = sep_y * bw;
                                    for x in (menu_x + padding)..(menu_x + menu_width - padding).min(bw) {
                                        buffer[row_start + x] = 0xFF555555;
                                    }
                                }
                            }
                        }

                        buffer.present().unwrap();
                    }
                }
            }
        }
    }

    fn get_interaction_window_id(&self, window_id: WindowId) -> Option<usize> {
        self.interaction_windows.iter().position(|iw| iw.window.id() == window_id)
    }

    fn get_pony_under_mouse_in_window(&self, iw_index: usize) -> Option<usize> {
        if let Some(iw) = self.interaction_windows.get(iw_index) {
            if iw.pony_index < self.ponies.len() {
                return Some(iw.pony_index);
            }
        }
        None
    }

    fn create_main_window(&mut self, event_loop: &winit::event_loop::ActiveEventLoop) {
        let selected_ids: HashSet<String> = if self.monitor_manager.selected_ids.is_empty() {
            self.monitor_manager.monitors.iter().map(|m| m.id.clone()).collect()
        } else {
            self.monitor_manager.selected_ids.iter().cloned().collect()
        };

        let mut max_x = 0i32;
        let mut max_y = 0i32;
        let mut min_x = i32::MAX;
        let mut min_y = i32::MAX;

        for monitor in &self.monitor_manager.monitors {
            if !selected_ids.contains(&monitor.id) { continue; }
            max_x = max_x.max(monitor.x + monitor.width as i32);
            max_y = max_y.max(monitor.y + monitor.height as i32);
            min_x = min_x.min(monitor.x);
            min_y = min_y.min(monitor.y);
        }

        let total_width = (max_x - min_x).max(800) as u32;
        let total_height = (max_y - min_y).max(600) as u32;

        let attrs = WindowAttributes::default()
            .with_title("Desktop Ponies Main")
            .with_decorations(false)
            .with_transparent(true)
            .with_inner_size(LogicalSize::new(total_width, total_height))
            .with_position(PhysicalPosition::new(min_x, min_y))
            .with_window_level(WindowLevel::AlwaysOnTop);

        if let Ok(window) = event_loop.create_window(attrs) {
            let pw = Arc::new(window);
            // Главное окно ВСЕГДА прозрачно для кликов
            pw.set_cursor_hittest(false).ok();

            if let Ok(ctx) = Context::new(pw.clone()) {
                if let Ok(surface) = Surface::new(&ctx, pw.clone()) {
                    self.main_surface = Some(surface);
                }
            }

            self.main_window = Some(pw);
            println!("[Main] Window created {}x{} at ({},{})", total_width, total_height, min_x, min_y);
        }
    }

    fn handle_click(&mut self, pony_index: usize, button: MouseButton, pressed: bool) {
        match button {
            MouseButton::Left => {
                if pressed {
                    self.mouse_down = true;

                    if self.context_menu.visible {
                        self.context_menu.hide();
                        return;
                    }

                    if pony_index < self.ponies.len() {
                        let pony_name = self.ponies[pony_index].config_name.clone();

                        // Сохраняем оригинальную длительность
                        {
                            let pony = &mut self.ponies[pony_index];
                            if pony.original_frame_duration.is_none() {
                                pony.original_frame_duration = Some(pony.frame_duration);
                            }
                            pony.grabbed = true;
                            pony.movement_type = MovementType::Dragged;
                        }

                        self.grabbed_pony = Some(pony_index);

                        // Загружаем drag-анимацию (отдельный блок заимствования)
                        self.set_pony_drag_animation(pony_index, &pony_name);

                        println!("[Drag] === DRAG STARTED for pony #{} '{}' ===",
                                 pony_index, pony_name);
                    }
                } else {
                    // Отпустили кнопку
                    self.mouse_down = false;
                    if let Some(idx) = self.grabbed_pony.take() {
                        if idx < self.ponies.len() {
                            let pony_name = self.ponies[idx].config_name.clone();

                            // Восстанавливаем idle анимацию
                            self.restore_pony_idle_animation(idx, &pony_name);

                            // Сбрасываем состояние
                            let pony = &mut self.ponies[idx];
                            pony.grabbed = false;
                            pony.movement_type = MovementType::None;
                            pony.behavior_timer = 0.0;

                            // Восстанавливаем оригинальную скорость анимации
                            if let Some(orig_dur) = pony.original_frame_duration {
                                pony.frame_duration = orig_dur;
                                pony.original_frame_duration = None;
                            }

                            println!("[Drag] === DRAG RELEASED for pony #{} '{}' ===",
                                     idx, pony_name);
                        }
                    }
                }
            }
            _ => {}
        }
    }

    fn set_pony_drag_animation(&mut self, pony_index: usize, pony_name: &str) {
        // Ищем drag-поведение НАПРЯМУЮ в конфиге (игнорируем available_behaviors)
        let drag_info = if let Some(config) = self.loader.get_config(pony_name) {
            config.behaviors.iter()
                .find(|b| b.name.to_lowercase().contains("drag"))
                .map(|behavior| {
                    let sprite_name = if !behavior.sprite_right.is_empty() {
                        behavior.sprite_right.clone()
                    } else {
                        behavior.sprite_left.clone()
                    };
                    println!("[Drag] Found drag behavior: '{}' using sprite '{}' (skip={})",
                             behavior.name, sprite_name, behavior.skip);
                    (sprite_name, behavior.name.clone())
                })
        } else {
            None
        };

        if let Some((sprite_name, behavior_name)) = drag_info {
            // ПРОВЕРЯЕМ существует ли файл спрайта
            let pony_dir = self.loader.ponies_dir.join(pony_name);
            let sprite_path = pony_dir.join(&sprite_name);

            if sprite_path.exists() {
                println!("[Drag] Loading sprite from: {:?}", sprite_path);
                let (frames, fc, w, h, delay) = self.loader.load_pony_frames(pony_name, &sprite_name);

                if !frames.is_empty() && !frames[0].is_empty() {
                    let pony = &mut self.ponies[pony_index];
                    pony.frames = frames;
                    pony.frame_count = fc;
                    pony.width = w;
                    pony.height = h;
                    pony.frame_duration = delay;
                    pony.current_frame = 0;
                    pony.current_behavior = behavior_name;
                    println!("[Drag] ✓ Loaded drag animation: {} frames, {}x{}", fc, w, h);
                    return;
                } else {
                    println!("[Drag] ✗ Failed to decode drag frames for '{}'", sprite_name);
                }
            } else {
                println!("[Drag] ✗ Sprite file not found: {:?}", sprite_path);
            }
        }

        // FALLBACK: Если нет drag-спрайтов, используем текущую анимацию с ускорением
        println!("[Drag] ⚠ No drag sprite for '{}', using speed-up effect", pony_name);
        let pony = &mut self.ponies[pony_index];
        // Ускоряем анимацию для эффекта "напряжения"
        pony.frame_duration = (pony.frame_duration * 0.4).max(0.03);
    }

    fn restore_pony_idle_animation(&mut self, pony_index: usize, pony_name: &str) {
        // Ищем idle/stand поведение НАПРЯМУЮ в конфиге
        let idle_info = if let Some(config) = self.loader.get_config(pony_name) {
            config.behaviors.iter()
                .find(|b| {
                    let name = b.name.to_lowercase();
                    name.contains("stand") || name.contains("idle") || name.contains("wake")
                })
                .map(|behavior| {
                    let sprite_name = if !behavior.sprite_right.is_empty() {
                        behavior.sprite_right.clone()
                    } else {
                        behavior.sprite_left.clone()
                    };
                    println!("[Drag] Found idle behavior: '{}' using sprite '{}' (skip={})",
                             behavior.name, sprite_name, behavior.skip);
                    (sprite_name, behavior.name.clone())
                })
        } else {
            None
        };

        if let Some((sprite_name, behavior_name)) = idle_info {
            let (frames, fc, w, h, delay) = self.loader.load_pony_frames(pony_name, &sprite_name);

            if !frames.is_empty() && !frames[0].is_empty() {
                let pony = &mut self.ponies[pony_index];
                pony.frames = frames;
                pony.frame_count = fc;
                pony.width = w;
                pony.height = h;
                pony.frame_duration = delay;
                pony.current_behavior = behavior_name;
                println!("[Drag] ✓ Restored idle animation: {} frames, {}x{}", fc, w, h);
                return;
            }
        }

        // Если не нашли idle - просто восстанавливаем оригинальную длительность
        println!("[Drag] ⚠ No idle behavior for '{}', restoring original duration", pony_name);
        let pony = &mut self.ponies[pony_index];
        if let Some(orig_dur) = pony.original_frame_duration {
            pony.frame_duration = orig_dur;
        }
    }

    fn execute_pony_action(&mut self, pony_index: usize, action: PonyAction) {
        if pony_index >= self.ponies.len() {
            return;
        }

        match action {
            PonyAction::Drag => {
                let pony = &mut self.ponies[pony_index];
                pony.grabbed = true;
                pony.movement_type = MovementType::Dragged;
                self.grabbed_pony = Some(pony_index);

                // По умолчанию просто уменьшаем скорость анимации
                if pony.original_frame_duration.is_none() {
                    pony.original_frame_duration = Some(pony.frame_duration);
                }
                pony.frame_duration *= 1.5; // Замедляем анимацию при драге

                println!("[Action] Drag pony #{}", pony_index);
            }
            PonyAction::Boop => {
                let p = &mut self.ponies[pony_index];
                p.vy = -250.0;
                p.vx = if fastrand::bool() { 100.0 } else { -100.0 };
                p.frame_timer = 0.0;
                p.movement_type = MovementType::HorizontalOnly;
                p.interaction_state = Some(InteractionState::Booped { timer: 2.0 });
                p.behavior_timer = 2.0;
                println!("[Action] Boop pony #{}", pony_index);
            }
            PonyAction::Feed => {
                let p = &mut self.ponies[pony_index];
                let speed_mult = 1.8;
                p.vx *= speed_mult;
                p.vy *= speed_mult;
                if p.original_frame_duration.is_none() {
                    p.original_frame_duration = Some(p.frame_duration);
                }
                p.frame_duration *= 0.6;
                p.interaction_state = Some(InteractionState::Fed {
                    timer: 3.0,
                    original_speed_mult: speed_mult,
                });
                p.behavior_timer = 3.0;
                println!("[Action] Feed pony #{}", pony_index);
            }
            PonyAction::Pet => {
                let p = &mut self.ponies[pony_index];
                p.vx = 0.0;
                p.vy = 0.0;
                p.movement_type = MovementType::None;
                if p.original_frame_duration.is_none() {
                    p.original_frame_duration = Some(p.frame_duration);
                }
                p.frame_duration *= 1.8;
                p.interaction_state = Some(InteractionState::Petted { timer: 4.0 });
                p.behavior_timer = 5.0;
                println!("[Action] Pet pony #{}", pony_index);
            }
            PonyAction::ChangeDirection => {
                let p = &mut self.ponies[pony_index];
                p.facing_right = !p.facing_right;
                p.vx *= -1.0;
                println!("[Action] Change direction pony #{}", pony_index);
            }
            PonyAction::ToggleSleep => {
                let p = &mut self.ponies[pony_index];
                let is_sleeping = matches!(p.interaction_state, Some(InteractionState::Sleeping));

                if is_sleeping {
                    p.interaction_state = None;
                    p.movement_type = MovementType::None;
                    p.behavior_timer = 0.0;
                    println!("[Action] Wake up pony #{}", pony_index);
                } else {
                    p.vx = 0.0;
                    p.vy = 0.0;
                    p.movement_type = MovementType::Sleep;
                    p.interaction_state = Some(InteractionState::Sleeping);
                    p.behavior_timer = 999999.0;
                    println!("[Action] Sleep pony #{}", pony_index);
                }
            }
            PonyAction::SendHome => {
                println!("[Action] Send home pony #{}", pony_index);
                // TODO: реализовать отправку домой
            }
        }
    }

    fn update_pony_interactions(&mut self, dt: f32) {
        for pony in &mut self.ponies {
            if let Some(ref mut state) = pony.interaction_state {
                match state {
                    InteractionState::Booped { ref mut timer } => {
                        *timer -= dt;
                        if *timer <= 0.0 {
                            pony.interaction_state = None;
                        }
                    }
                    InteractionState::Fed { ref mut timer, original_speed_mult } => {
                        *timer -= dt;
                        if *timer <= 0.0 {
                            let mult = *original_speed_mult;
                            pony.vx /= mult;
                            pony.vy /= mult;
                            if let Some(orig_dur) = pony.original_frame_duration {
                                pony.frame_duration = orig_dur;
                                pony.original_frame_duration = None;
                            }
                            pony.interaction_state = None;
                        }
                    }
                    InteractionState::Petted { ref mut timer } => {
                        *timer -= dt;
                        if *timer <= 0.0 {
                            if let Some(orig_dur) = pony.original_frame_duration {
                                pony.frame_duration = orig_dur;
                                pony.original_frame_duration = None;
                            }
                            pony.behavior_timer = 0.0;
                            pony.interaction_state = None;
                        }
                    }
                    InteractionState::Sleeping => {
                        pony.vx = 0.0;
                        pony.vy = 0.0;
                        pony.movement_type = MovementType::Sleep;
                    }
                }
            }
        }
    }

    fn render_all_windows(&mut self) {
        let frame_duration = std::time::Duration::from_secs_f64(1.0 / self.fps_limit as f64);
        if self.frame_timer.elapsed() < frame_duration {
            return;
        }
        self.frame_timer = Instant::now();

        let now = Instant::now();
        let dt = now.duration_since(self.last_frame).as_secs_f32().min(0.05);
        self.last_frame = now;

        self.update_pony_interactions(dt);
        self.update_interaction_windows();
        self.render_interaction_windows();

        let (screen_w, screen_h) = self.main_window.as_ref()
            .map(|w| {
                let size = w.inner_size();
                (size.width as f32, size.height as f32)
            })
            .unwrap_or((1920.0, 1080.0));

        update_ponies(
            &mut self.ponies,
            &mut self.loader,
            dt,
            screen_w,
            screen_h,
            self.mouse_x,
            self.mouse_y,
            self.mouse_down,
            &mut self.grabbed_pony,
        );

        // Рисуем главное окно (самих пони)
        if let Some(surface) = &mut self.main_surface {
            if let Some(window) = &self.main_window {
                let size = window.inner_size();
                if let (Some(sw), Some(sh)) = (NonZeroU32::new(size.width), NonZeroU32::new(size.height)) {
                    surface.resize(sw, sh).unwrap();
                    let mut buffer = surface.buffer_mut().unwrap();
                    let bw = sw.get() as usize;
                    let bh = sh.get() as usize;
                    buffer.fill(0x00000000);

                    // Рисуем пони
                    for p in &self.ponies {
                        if p.current_frame as usize >= p.frames.len() { continue; }
                        let frame = &p.frames[p.current_frame as usize];
                        let fw = p.width as usize;

                        let x0 = p.x.max(0.0) as usize;
                        let y0 = p.y.max(0.0) as usize;
                        let x1 = ((p.x + p.width as f32).min(bw as f32)).max(0.0) as usize;
                        let y1 = ((p.y + p.height as f32).min(bh as f32)).max(0.0) as usize;

                        for by in y0..y1 {
                            let py = by - p.y as usize;
                            let row_offset = by * bw;
                            let frame_row = py * fw;
                            for bx in x0..x1 {
                                let px = bx - p.x as usize;
                                let src_x = if !p.facing_right { fw - 1 - px } else { px };
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
        }

        // Рисуем контекстное меню ПОВЕРХ пони (после презентации основного буфера)
        self.render_context_menu();

        self.frame_counter += 1;
        self.perf.update(self.ponies.len(), 0);
        if self.frame_counter % 60 == 0 {
            println!("[Stats] {} | Windows: {}", self.perf.stats_string(), self.interaction_windows.len());
        }
    }
}

// ==================== UPDATE PONIES ====================

fn change_pony_behavior(pony: &mut Pony, loader: &mut DesktopPoniesLoader) {
    // Не меняем поведение если пони схвачен или спит/поглажен
    if pony.grabbed { return; }
    if pony.interaction_state.is_some() { return; }
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
    grabbed_pony: &mut Option<usize>,
) {
    for i in 0..ponies.len() {
        let p = &mut ponies[i];

        if p.grabbed {
            if mouse_down {
                p.x = (mouse_x - p.width as f32 / 2.0).max(0.0).min(screen_width - p.width as f32);
                p.y = (mouse_y - p.height as f32 / 2.0).max(0.0).min(screen_height - p.height as f32);
                p.vx = 0.0;
                p.vy = 0.0;
            } else {
                p.grabbed = false;
                p.movement_type = MovementType::None;
                p.behavior_timer = 0.0;

                // Восстанавливаем оригинальную скорость анимации
                if let Some(orig_dur) = p.original_frame_duration {
                    p.frame_duration = orig_dur;
                    p.original_frame_duration = None;
                }

                *grabbed_pony = None;
            }
            p.frame_timer += dt;
            while p.frame_timer >= p.frame_duration {
                p.frame_timer -= p.frame_duration;
                p.current_frame = (p.current_frame + 1) % p.frame_count;
            }
            continue;
        }

        let is_sleeping = matches!(p.interaction_state, Some(InteractionState::Sleeping));
        let is_petted = matches!(p.interaction_state, Some(InteractionState::Petted { .. }));

        if !is_sleeping && !is_petted {
            p.behavior_timer -= dt;
            if p.behavior_timer <= 0.0 {
                change_pony_behavior(p, loader);
            }
        }

        if is_sleeping {
            p.vx = 0.0;
            p.vy = 0.0;
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

// ==================== APPLICATION HANDLER ====================

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

        // Создаём UI окно
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

        // Создаём главное окно
        if self.main_window.is_none() {
            self.create_main_window(event_loop);
        }
    }

    fn window_event(&mut self, event_loop: &winit::event_loop::ActiveEventLoop, window_id: WindowId, event: WindowEvent) {
        let ui_id = self.ui_window.as_ref().map(|w| w.id());
        let main_id = self.main_window.as_ref().map(|w| w.id());
        let interaction_window_idx = self.get_interaction_window_id(window_id);

        match event {
            WindowEvent::CloseRequested if Some(window_id) == ui_id => {
                // Сохраняем настройки перед выходом
                self.settings.save(&self.settings_path);
                event_loop.exit();
            }

            // Курсор в главном окне
            WindowEvent::CursorMoved { position, .. } if Some(window_id) == main_id => {
                self.mouse_x = position.x as f32;
                self.mouse_y = position.y as f32;
            }

            // Клики в окнах взаимодействия
            WindowEvent::MouseInput { state, button, .. } if interaction_window_idx.is_some() => {
                let pressed = state == ElementState::Pressed;
                let iw_idx = interaction_window_idx.unwrap();

                if let Some(pony_idx) = self.get_pony_under_mouse_in_window(iw_idx) {
                    println!("[Click] Window #{} on pony #{}: {:?} pressed={}",
                             iw_idx, pony_idx, button, pressed);
                    self.handle_click(pony_idx, button, pressed);
                }
            }

            // Движение мыши в окне взаимодействия
            WindowEvent::CursorMoved { position, .. } if interaction_window_idx.is_some() => {
                let iw_idx = interaction_window_idx.unwrap();
                if let Some(iw) = self.interaction_windows.get(iw_idx) {
                    if let Ok(window_pos) = iw.window.outer_position() {
                        if let Some(main_window) = &self.main_window {
                            if let Ok(main_pos) = main_window.outer_position() {
                                self.mouse_x = (window_pos.x - main_pos.x) as f32 + position.x as f32;
                                self.mouse_y = (window_pos.y - main_pos.y) as f32 + position.y as f32;
                            }
                        }
                    }
                }
            }

            WindowEvent::RedrawRequested => {
                // Спавним пони из очереди
                let to_spawn: Vec<String> = self.spawn_queue.lock().unwrap().drain(..).collect();
                for name in to_spawn {
                    self.spawn_pony(&name, event_loop);
                }

                self.render_all_windows();

                // Запрашиваем перерисовку
                if let Some(w) = &self.main_window { w.request_redraw(); }
                for iw in &self.interaction_windows {
                    iw.window.request_redraw();
                }
            }
            _ => {}
        }
    }

    fn user_event(&mut self, event_loop: &winit::event_loop::ActiveEventLoop, event: UserEvent) {
        match event {
            UserEvent::RequestRedraw => {
                if let Some(w) = &self.main_window { w.request_redraw(); }
            }
            UserEvent::UpdateInteractionWindows => {
                self.update_interaction_windows();
            }
            UserEvent::ReloadMonitors => {
                self.monitor_manager.detect(event_loop);
                if self.monitor_manager.selected_ids.is_empty() {
                    self.monitor_manager.selected_ids = self.monitor_manager.monitors.iter()
                        .map(|m| m.id.clone()).collect();
                }

                // Удаляем старые окна
                self.interaction_windows.clear();
                self.main_window = None;
                self.main_surface = None;

                // Пересоздаём
                self.create_main_window(event_loop);
                for i in 0..self.ponies.len() {
                    self.create_interaction_window(i, event_loop);
                }
            }
            UserEvent::ApplySettings { selected_monitors } => {
                self.settings.selected_monitors = selected_monitors.iter().cloned().collect();
                self.monitor_manager.selected_ids = selected_monitors;
                self.settings.save(&self.settings_path);

                self.interaction_windows.clear();
                self.main_window = None;
                self.main_surface = None;

                self.create_main_window(event_loop);
                for i in 0..self.ponies.len() {
                    self.create_interaction_window(i, event_loop);
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

// ==================== MAIN ====================

fn main() {
    println!("Desktop Ponies RS - Starting...");

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

    let proxy_clone = proxy.clone();
    std::thread::spawn(move || {
        loop {
            std::thread::sleep(std::time::Duration::from_millis(16)); // ~60 FPS
            let _ = proxy_clone.send_event(UserEvent::UpdateInteractionWindows);
        }
    });

    el.run_app(&mut App {
        ponies: Vec::new(),
        main_window: None,
        main_surface: None,
        interaction_windows: Vec::new(),
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
        right_mouse_down: false,
        grabbed_pony: None,
        context_menu: ContextMenu::new(),
        perf: PerformanceMonitor::new(),
        frame_counter: 0,
        fps_limit: 60,
        frame_timer: Instant::now(),
        debug_hitboxes: true,
    }).unwrap();
}