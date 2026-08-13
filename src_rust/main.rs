#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
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
mod editor;
mod bitmap_font;

use loader::{DesktopPoniesLoader, MovementType, Behavior, GifAnimation, GifFrameData};
use monitor_manager::MonitorManager;
use settings::AppSettings;
use performance::PerformanceMonitor;
use context_menu::{ContextMenu, PonyAction};
use crate::editor::EditorWindow;

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

// НОВАЯ СТРУКТУРА PONY С ПОДДЕРЖКОЙ ИНДИВИДУАЛЬНЫХ ЗАДЕРЖЕК КАДРОВ
struct Pony {
    x: f32, y: f32,
    vx: f32, vy: f32,
    animation: GifAnimation,
    current_frame: usize,
    frame_timer: f32,
    animation_speed_mult: f32,
    prevent_loop: bool,
    fixed_fps: Option<f32>,
    width: u32, height: u32,
    facing_right: bool,
    config_name: String,
    current_behavior: String,
    available_behaviors: Vec<Behavior>,
    movement_type: MovementType,
    behavior_timer: f32,
    grabbed: bool,
    interaction_state: Option<InteractionState>,
    original_frame_duration: Option<f32>,
    // НОВОЕ ПОЛЕ: счётчик повторений текущей анимации
    current_behavior_repeat_count: u32,
}

struct InteractionWindow {
    window: Arc<winit::window::Window>,
    surface: Surface<Arc<winit::window::Window>, Arc<winit::window::Window>>,
    pony_index: usize,
}

// ДОБАВЛЕНО: отдельное окно-хитбокс для контекстного меню, по аналогии с
// InteractionWindow у каждого пони. Раньше клики по пунктам меню ловились
// через временное включение cursor_hittest(true) на ГЛАВНОМ окне целиком
// (см. историю в close_context_menu/handle_click) — это грубый обходной
// путь: пока меню открыто, главное окно переставало быть "прозрачным для
// кликов" на всей своей площади, что могло цеплять клики совсем не по
// меню. Теперь у меню своё маленькое AlwaysOnTop-окно, всегда кликабельное,
// а главное окно остаётся click-through постоянно.
struct MenuWindow {
    window: Arc<winit::window::Window>,
    surface: Surface<Arc<winit::window::Window>, Arc<winit::window::Window>>,
}

struct App {
    ponies: Vec<Pony>,
    main_window: Option<Arc<winit::window::Window>>,
    main_surface: Option<Surface<Arc<winit::window::Window>, Arc<winit::window::Window>>>,
    interaction_windows: Vec<InteractionWindow>,
    // ДОБАВЛЕНО: отдельный хитбокс контекстного меню (см. MenuWindow выше).
    menu_window: Option<MenuWindow>,
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
    // ДОБАВЛЕНО: локальные координаты мыши относительно окна-хитбокса
    // меню (0,0 — левый верхний угол меню) — отдельно от mouse_x/mouse_y,
    // которые остаются в системе координат главного окна и используются
    // для пони/interaction-окон.
    menu_mouse_x: f32,
    menu_mouse_y: f32,
    perf: PerformanceMonitor,
    frame_counter: u64,
    fps_limit: u32,
    frame_timer: Instant,
    debug_hitboxes: bool,
}

// ==================== ФУНКЦИЯ ЗАПУСКА РЕДАКТОРА ====================

fn launch_editor() {
    println!("[Editor] Launching Pony Editor...");

    let exe_path = match std::env::current_exe() {
        Ok(path) => path,
        Err(e) => {
            eprintln!("[Editor] Failed to get exe path: {}", e);
            return;
        }
    };

    match std::process::Command::new(exe_path)
        .arg("--editor")
        .spawn()
    {
        Ok(child) => {
            println!("[Editor] Editor started with PID: {}", child.id());
        }
        Err(e) => {
            eprintln!("[Editor] Failed to launch editor: {}", e);
        }
    }
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
        // ИСПРАВЛЕНО: лимит пони был захардкожен (50) и игнорировал
        // settings.pony_limit, настраиваемый пользователем/UI.
        let pony_limit = self.settings.pony_limit.max(1);
        while self.ponies.len() >= pony_limit {
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

        let animation = self.loader.load_pony_frames(name, &sprite_name);
        // ИСПРАВЛЕНО: раньше здесь тоже брался полностью случайный угол
        // 0..360° вне зависимости от типа движения поведения — см. подробный
        // комментарий у random_velocity_for_movement(). Сначала определяем
        // movement_type (он же используется ниже для самого поля Pony), и
        // считаем вектор скорости через тот же helper, что и при смене
        // поведения — так поведение только что заспавненного пони сразу
        // соответствует своему типу движения, а не общей "диагонали".
        let spawn_movement_type = MovementType::parse(&first_behavior.movement);
        let speed = match spawn_movement_type {
            MovementType::None | MovementType::Sleep => 0.0,
            _ => first_behavior.speed * 60.0,
        };
        let (spawn_vx, spawn_vy) = random_velocity_for_movement(&spawn_movement_type, speed);

        let (screen_w, screen_h) = self.main_window.as_ref()
            .map(|w| {
                let size = w.inner_size();
                (size.width as f32, size.height as f32)
            })
            .unwrap_or((1920.0, 1080.0));

        let pony_index = self.ponies.len();

        // Применяем настройки анимации из поведения
        let animation_speed_mult = first_behavior.set_animation_speed.unwrap_or(1.0);
        // ИСПРАВЛЕНО: тот же баг с перепутанными полями ini, что и в
        // change_pony_behavior() — здесь бралось do_not_repeat_animations
        // вместо настоящего prevent_loop, из-за чего только что заспавненный
        // пони мог зацикливать гифку, даже если в .ini prevent_loop=true.
        let prevent_loop = first_behavior.prevent_loop;
        let fixed_fps = first_behavior.set_fps;

        // Сохраняем размеры ДО перемещения animation
        let width = animation.width;
        let height = animation.height;

        self.ponies.push(Pony {
            x: fastrand::f32() * (screen_w - 200.0) + 100.0,
            y: fastrand::f32() * (screen_h - 200.0) + 100.0,
            vx: spawn_vx,
            vy: spawn_vy,
            animation,  // перемещаем здесь
            current_frame: 0,
            frame_timer: 0.0,
            animation_speed_mult,
            prevent_loop,
            fixed_fps,
            width,      // используем сохраненное значение
            height,     // используем сохраненное значение
            facing_right,
            config_name: name.to_string(),
            current_behavior: first_behavior.name.clone(),
            available_behaviors,
            movement_type: spawn_movement_type,
            behavior_timer: first_behavior.min_duration + fastrand::f32() * (first_behavior.max_duration - first_behavior.min_duration),
            grabbed: false,
            interaction_state: None,
            original_frame_duration: None,
            current_behavior_repeat_count: 0,
        });

        self.create_interaction_window(pony_index, event_loop);
        self.update_interaction_windows();

        println!("[Spawn] Created pony '{}' (#{}) at ({:.0},{:.0}) with interaction window, frames: {}, delays: {}",
                 name, pony_index, self.ponies[pony_index].x, self.ponies[pony_index].y,
                 self.ponies[pony_index].animation.frames.len(),
                 self.ponies[pony_index].animation.frames.iter().map(|f| f.delay).collect::<Vec<_>>().len());
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
            pw.set_cursor_hittest(true).ok();

            if let Ok(ctx) = Context::new(pw.clone()) {
                if let Ok(mut surface) = Surface::new(&ctx, pw.clone()) {
                    if let (Some(w), Some(h)) = (
                        NonZeroU32::new(window_w as u32),
                        NonZeroU32::new(window_h as u32)
                    ) {
                        surface.resize(w, h).unwrap();
                        let mut buffer = surface.buffer_mut().unwrap();
                        let blue_color = 0x00000000;
                        buffer.fill(blue_color);
                        buffer.present().unwrap();
                    }

                    self.interaction_windows.push(InteractionWindow {
                        window: pw.clone(),
                        surface,
                        pony_index,
                    });

                    pw.set_visible(true);

                    println!("[Interaction] Created and SHOWN window for pony #{} ({}x{})",
                             pony_index, window_w, window_h);
                }
            }
        } else {
            eprintln!("[Error] Failed to create interaction window for pony #{}", pony_index);
        }
    }

    // ДОБАВЛЕНО: создаёт отдельное окно-хитбокс для контекстного меню,
    // позиционированное поверх текущих координат self.context_menu
    // (которые уже выставлены вызовом ContextMenu::show() перед этим).
    // Координаты меню (context_menu.x/y) хранятся в системе координат
    // главного окна — переводим их в экранные так же, как это делает
    // update_interaction_windows() для окон пони.
    fn create_menu_window(&mut self, event_loop: &winit::event_loop::ActiveEventLoop) {
        self.destroy_menu_window();

        let (menu_w, menu_h) = context_menu::menu_size(self.context_menu.items.len());

        let main_pos = self.main_window.as_ref()
            .and_then(|w| w.outer_position().ok())
            .unwrap_or(PhysicalPosition::new(0, 0));

        let screen_x = main_pos.x + self.context_menu.x as i32;
        let screen_y = main_pos.y + self.context_menu.y as i32;

        let attrs = WindowAttributes::default()
            .with_title("Pony Context Menu")
            .with_decorations(false)
            .with_transparent(true)
            .with_visible(false)
            .with_inner_size(LogicalSize::new(menu_w as f64, menu_h as f64))
            .with_position(PhysicalPosition::new(screen_x, screen_y))
            .with_window_level(WindowLevel::AlwaysOnTop);

        if let Ok(window) = event_loop.create_window(attrs) {
            let mw = Arc::new(window);
            // Постоянно кликабельное окно — это и есть тот самый отдельный
            // хитбокс, который просил пользователь (аналог InteractionWindow).
            mw.set_cursor_hittest(true).ok();

            if let Ok(ctx) = Context::new(mw.clone()) {
                if let Ok(surface) = Surface::new(&ctx, mw.clone()) {
                    self.menu_window = Some(MenuWindow { window: mw.clone(), surface });
                    mw.set_visible(true);
                    println!("[Menu] Hitbox window created at ({},{}) {}x{}", screen_x, screen_y, menu_w, menu_h);
                }
            }
        } else {
            eprintln!("[Error] Failed to create context menu hitbox window");
        }
    }

    fn destroy_menu_window(&mut self) {
        if let Some(mw) = self.menu_window.take() {
            mw.window.set_visible(false);
        }
    }

    // ДОБАВЛЕНО: нужно для подменю "Add Pony" — когда список пунктов меню
    // меняется БЕЗ закрытия окна (переход в подменю выбора пони и обратно),
    // сам OS-размер окна-хитбокса тоже надо подогнать под новое число
    // пунктов, иначе окно останется прежнего (меньшего/большего) размера, и
    // часть пунктов физически не поместится в кликабельную область.
    fn resize_menu_window_for_items(&mut self) {
        if let Some(mw) = &self.menu_window {
            let (w, h) = context_menu::menu_size(self.context_menu.items.len());
            let _ = mw.window.request_inner_size(PhysicalSize::new(w, h));
        }
    }

    fn remove_pony(&mut self, index: usize, _event_loop: &winit::event_loop::ActiveEventLoop) {
        if index < self.ponies.len() {
            println!("[Remove] Removing pony #{}", index);

            if let Some(iw_idx) = self.interaction_windows.iter().position(|iw| iw.pony_index == index) {
                self.interaction_windows[iw_idx].window.set_visible(false);
                println!("[Remove] Hidden interaction window for pony #{}", index);
            }

            self.interaction_windows.retain(|iw| iw.pony_index != index);

            for iw in &mut self.interaction_windows {
                if iw.pony_index > index {
                    iw.pony_index -= 1;
                }
            }

            self.ponies.remove(index);

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

                        let _ = iw.window.set_outer_position(PhysicalPosition::new(x.max(0), y.max(0)));
                        let _ = iw.window.request_inner_size(PhysicalSize::new(w, h));

                        // ИСПРАВЛЕНО: раньше окно-хитбокс пони принудительно скрывалось
                        // на время сна (should_show = !is_sleeping) — из-за этого
                        // спящего пони нельзя было ни навести, ни кликнуть правой
                        // кнопкой, чтобы разбудить: хитбокс буквально пропадал с
                        // экрана, хотя сам пони оставался виден на главном окне.
                        // Хитбокс должен оставаться кликабельным всегда, пока пони
                        // не удалён — сон не должен отключать взаимодействие с ним.
                        let is_visible = iw.window.is_visible().unwrap_or(false);
                        if !is_visible {
                            iw.window.set_visible(true);
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
                        let blue_color = 0x00000000;
                        buffer.fill(blue_color);

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

    // ИСПРАВЛЕНО: полностью переписано под отдельное окно-хитбокс меню.
    // Раньше меню рисовалось поверх поверхности главного окна абсолютными
    // координатами (menu_x/menu_y) — теперь рисуется в СВОЁМ окне локальными
    // координатами (0,0 — левый верхний угол), размер окна = размеру меню.
    //
    // ИСПРАВЛЕНО (текст): раньше пункты меню были просто закрашенными
    // прямоугольниками без единой буквы ("просто окошко" — как и заметил
    // пользователь), потому что softbuffer не умеет рисовать текст сам по
    // себе, и никакой текстовый рендеринг реализован не был. Теперь подписи
    // рисуются через bitmap_font::draw_text (см. src_rust/bitmap_font.rs).
    //
    // ИСПРАВЛЕНО (оформление): цветовая схема переведена на светлую
    // Win10-подобную (светло-серый фон, тонкая серая рамка, светло-голубое
    // выделение при наведении с голубой рамкой) вместо тёмной Catppuccin-схемы.
    fn render_context_menu(&mut self) {
        if !self.context_menu.visible {
            return;
        }

        let Some(mw) = &mut self.menu_window else { return; };

        let (menu_w, menu_h) = context_menu::menu_size(self.context_menu.items.len());
        let (Some(sw), Some(sh)) = (NonZeroU32::new(menu_w), NonZeroU32::new(menu_h)) else { return; };

        if mw.surface.resize(sw, sh).is_err() {
            return;
        }

        if let Ok(mut buffer) = mw.surface.buffer_mut() {
            let bw = sw.get() as usize;
            let bh = sh.get() as usize;

            // Палитра в духе классического контекстного меню Windows 10.
            let bg_color: u32 = 0xFFF3F3F3;
            let border_color: u32 = 0xFF8B8B8B;
            let hover_bg: u32 = 0xFFE0EEFB;
            let hover_border: u32 = 0xFFA6D8FF;
            let text_color: u32 = 0xFF1B1B1B;
            let disabled_text_color: u32 = 0xFFA3A3A3;
            let sep_color: u32 = 0xFFE3E3E3;

            for y in 0..bh {
                let row = y * bw;
                let is_h_border = y == 0 || y == bh - 1;
                for x in 0..bw {
                    let is_border = is_h_border || x == 0 || x == bw - 1;
                    buffer[row + x] = if is_border { border_color } else { bg_color };
                }
            }

            let hover_idx = self.context_menu.hit_test(self.menu_mouse_x, self.menu_mouse_y);
            let item_h = context_menu::ITEM_HEIGHT as usize;
            let padding = context_menu::MENU_PADDING as usize;
            let item_count = self.context_menu.items.len();

            for i in 0..item_count {
                let item_y = padding + i * item_h;
                let item = &self.context_menu.items[i];
                let is_hover = Some(i) == hover_idx && item.enabled;

                if is_hover {
                    let y0 = item_y;
                    let y1 = (item_y + item_h).min(bh.saturating_sub(1));
                    for y in y0..y1 {
                        let row = y * bw;
                        for x in 2..bw.saturating_sub(2) {
                            buffer[row + x] = hover_bg;
                        }
                    }
                    if y0 < bh {
                        let row = y0 * bw;
                        for x in 2..bw.saturating_sub(2) { buffer[row + x] = hover_border; }
                    }
                    if y1 > 0 && y1 - 1 < bh {
                        let row = (y1 - 1) * bw;
                        for x in 2..bw.saturating_sub(2) { buffer[row + x] = hover_border; }
                    }
                }

                let color = if item.enabled { text_color } else { disabled_text_color };
                let text_y = item_y as i32 + (item_h as i32 - bitmap_font::GLYPH_H) / 2;
                bitmap_font::draw_text(&mut buffer, bw, bh, padding as i32 + 8, text_y, &item.label, color, 1);

                if i < item_count - 1 {
                    let sep_y = item_y + item_h - 1;
                    if sep_y < bh {
                        let row = sep_y * bw;
                        for x in (padding + 4)..bw.saturating_sub(padding + 4) {
                            buffer[row + x] = sep_color;
                        }
                    }
                }
            }

            let _ = buffer.present();
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

    // ИСПРАВЛЕНО: правая кнопка мыши раньше вообще не обрабатывалась, поэтому
    // ContextMenu::show()/execute_pony_action() никогда не вызывались, и всё
    // контекстное меню (Взять/Боп/Покормить/Погладить/...) было недоступно.
    //
    // ИСПРАВЛЕНО (хитбокс меню): раньше здесь же временно возвращали
    // cursor_hittest(false) главному окну — это была обратная сторона
    // временного включения hit-test на главном окне при открытии меню.
    // Теперь у меню собственное окно (MenuWindow), поэтому главное окно
    // просто никогда не трогается — оно всегда click-through.
    fn close_context_menu(&mut self) {
        self.context_menu.hide();
        self.destroy_menu_window();
    }

    fn handle_click(&mut self, pony_index: usize, button: MouseButton, pressed: bool, event_loop: &winit::event_loop::ActiveEventLoop) {
        match button {
            MouseButton::Left => {
                if pressed {
                    self.mouse_down = true;

                    // ИСПРАВЛЕНО: раньше здесь пытались вычислить пункт меню
                    // из hit_test(self.mouse_x, self.mouse_y) — координат
                    // мыши В ГЛАВНОМ ОКНЕ — хотя это событие приходит с
                    // interaction-окна конкретного пони, а не с окна меню.
                    // Теперь у меню отдельный хитбокс (см. WindowEvent для
                    // menu_window_idx ниже), где клики по пунктам меню
                    // обрабатываются с правильными локальными координатами.
                    // Клик по пони, пока меню открыто, просто закрывает меню
                    // (стандартное поведение — клик "мимо" меню его закрывает).
                    if self.context_menu.visible {
                        self.close_context_menu();
                        return;
                    }

                    if pony_index < self.ponies.len() {
                        let pony_name = self.ponies[pony_index].config_name.clone();

                        {
                            let pony = &mut self.ponies[pony_index];
                            if pony.original_frame_duration.is_none() {
                                pony.original_frame_duration = Some(pony.animation.default_delay);
                            }
                            pony.grabbed = true;
                            pony.movement_type = MovementType::Dragged;
                        }

                        self.grabbed_pony = Some(pony_index);
                        self.set_pony_drag_animation(pony_index, &pony_name);

                        println!("[Drag] === DRAG STARTED for pony #{} '{}' ===",
                                 pony_index, pony_name);
                    }
                } else {
                    self.mouse_down = false;
                    if let Some(idx) = self.grabbed_pony.take() {
                        if idx < self.ponies.len() {
                            let pony_name = self.ponies[idx].config_name.clone();

                            self.restore_pony_idle_animation(idx, &pony_name);

                            let pony = &mut self.ponies[idx];
                            pony.grabbed = false;
                            pony.movement_type = MovementType::None;
                            pony.behavior_timer = 0.0;

                            if let Some(orig_dur) = pony.original_frame_duration {
                                pony.animation.default_delay = orig_dur;
                                pony.original_frame_duration = None;
                            }

                            println!("[Drag] === DRAG RELEASED for pony #{} '{}' ===",
                                     idx, pony_name);
                        }
                    }
                }
            }
            MouseButton::Right => {
                if pressed {
                    if self.context_menu.visible {
                        self.close_context_menu();
                    } else if pony_index < self.ponies.len() {
                        let pony_name = self.ponies[pony_index].config_name.clone();
                        // ДОБАВЛЕНО: подписи Sleep/Pause и Sleep/Pause All
                        // должны переключаться в зависимости от текущего
                        // состояния (как в оригинале, DisplayPonyMenu) —
                        // считаем состояние прямо перед открытием меню.
                        let is_sleeping = matches!(self.ponies[pony_index].interaction_state, Some(InteractionState::Sleeping));
                        let all_sleeping = !self.ponies.is_empty()
                            && self.ponies.iter().all(|p| matches!(p.interaction_state, Some(InteractionState::Sleeping)));
                        self.context_menu.show(self.mouse_x, self.mouse_y, pony_index, &pony_name, is_sleeping, all_sleeping);
                        // ДОБАВЛЕНО: отдельный хитбокс для меню вместо
                        // временного hit-test на главном окне.
                        self.create_menu_window(event_loop);
                        println!("[Menu] Opened context menu for pony #{} '{}'", pony_index, pony_name);
                    }
                }
            }
            _ => {}
        }
    }

    fn set_pony_drag_animation(&mut self, pony_index: usize, pony_name: &str) {
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
                    (sprite_name, behavior.name.clone(), behavior.set_animation_speed, behavior.set_fps)
                })
        } else {
            None
        };

        if let Some((sprite_name, behavior_name, anim_speed, fps)) = drag_info {
            let pony_dir = self.loader.ponies_dir.join(pony_name);
            let sprite_path = pony_dir.join(&sprite_name);

            if sprite_path.exists() {
                println!("[Drag] Loading sprite from: {:?}", sprite_path);
                let animation = self.loader.load_pony_frames(pony_name, &sprite_name);

                if !animation.frames.is_empty() && !animation.frames[0].data.is_empty() {
                    let pony = &mut self.ponies[pony_index];
                    pony.animation = animation;
                    pony.width = pony.animation.width;
                    pony.height = pony.animation.height;
                    pony.current_frame = 0;
                    pony.frame_timer = 0.0;
                    pony.current_behavior = behavior_name;
                    pony.animation_speed_mult = anim_speed.unwrap_or(1.0);
                    pony.fixed_fps = fps;
                    println!("[Drag] ✓ Loaded drag animation: {} frames, {}x{}",
                             pony.animation.frames.len(), pony.width, pony.height);
                    return;
                } else {
                    println!("[Drag] ✗ Failed to decode drag frames for '{}'", sprite_name);
                }
            } else {
                println!("[Drag] ✗ Sprite file not found: {:?}", sprite_path);
            }
        }

        // ИСПРАВЛЕНО: settings.drag_behavior_fallback раньше нигде не читался,
        // поэтому ускоряющий "фолбэк" при отсутствии drag-спрайта включался
        // всегда, даже если пользователь отключил его в настройках.
        if !self.settings.drag_behavior_fallback {
            println!("[Drag] ⚠ No drag sprite for '{}', fallback disabled in settings", pony_name);
            return;
        }

        println!("[Drag] ⚠ No drag sprite for '{}', using speed-up effect", pony_name);
        let pony = &mut self.ponies[pony_index];
        pony.animation_speed_mult = 2.5;
    }

    fn restore_pony_idle_animation(&mut self, pony_index: usize, pony_name: &str) {
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
                    (sprite_name, behavior.name.clone(), behavior.set_animation_speed, behavior.set_fps)
                })
        } else {
            None
        };

        if let Some((sprite_name, behavior_name, anim_speed, fps)) = idle_info {
            let animation = self.loader.load_pony_frames(pony_name, &sprite_name);

            if !animation.frames.is_empty() && !animation.frames[0].data.is_empty() {
                let pony = &mut self.ponies[pony_index];
                pony.animation = animation;
                pony.width = pony.animation.width;
                pony.height = pony.animation.height;
                pony.current_frame = 0;
                pony.frame_timer = 0.0;
                pony.current_behavior = behavior_name;
                pony.animation_speed_mult = anim_speed.unwrap_or(1.0);
                pony.fixed_fps = fps;
                println!("[Drag] ✓ Restored idle animation: {} frames, {}x{}",
                         pony.animation.frames.len(), pony.width, pony.height);
                return;
            }
        }

        println!("[Drag] ⚠ No idle behavior for '{}', restoring original settings", pony_name);
        let pony = &mut self.ponies[pony_index];
        pony.animation_speed_mult = 1.0;
        pony.fixed_fps = None;
        if let Some(orig_dur) = pony.original_frame_duration {
            pony.animation.default_delay = orig_dur;
        }
    }

    // ИЗМЕНЕНО: набор действий меню ПКМ сокращён по запросу пользователя —
    // вместо Drag/Boop/Feed/Pet/ChangeDirection теперь Remove/ToggleSleep/
    // ToggleSleepAll/AddPony/ReturnToMenu/Exit. Понадобился event_loop
    // (для Exit и для remove_pony/create_menu_window по цепочке), поэтому
    // сигнатура расширена — единственный вызов (в window_event) его уже имеет.
    fn execute_pony_action(&mut self, pony_index: usize, action: PonyAction, event_loop: &winit::event_loop::ActiveEventLoop) {
        match action {
            PonyAction::Remove => {
                if pony_index < self.ponies.len() {
                    println!("[Action] Remove pony #{}", pony_index);
                    self.remove_pony(pony_index, event_loop);
                }
            }
            // ДОБАВЛЕНО: соответствует "Remove Every {name}" в оригинале
            // (DesktopPonyAnimator.vb) — удаляет ВСЕ заспавненные копии
            // именно этого пони (сравнение по имени конфига), а не только
            // ту, по которой кликнули правой кнопкой. Раньше такого пункта
            // не было вообще.
            PonyAction::RemoveEvery => {
                if pony_index >= self.ponies.len() { return; }
                let target_name = self.ponies[pony_index].config_name.clone();
                let mut indices: Vec<usize> = self.ponies.iter().enumerate()
                    .filter(|(_, p)| p.config_name == target_name)
                    .map(|(i, _)| i)
                    .collect();
                // Удаляем от старшего индекса к младшему, чтобы удаление
                // одного пони не сдвигало индексы ещё не обработанных.
                indices.sort_unstable_by(|a, b| b.cmp(a));
                println!("[Action] Remove Every ({}) → {} ponies", target_name, indices.len());
                for idx in indices {
                    self.remove_pony(idx, event_loop);
                }
            }
            // ИСПРАВЛЕНО: раньше "сон" просто замораживал текущий кадр
            // (animation_speed_mult = 0.0) поверх ЛЮБОЙ анимации, которая
            // играла в момент клика — пони застывал статичной картинкой той
            // анимации, что была активна, а не показывал анимацию сна. Теперь
            // enter_sleep()/wake_up() переключают на настоящее Sleep-поведение
            // из .ini (как _sleepBehavior в оригинале, Pony.vb) — гифка сна
            // проигрывается по-настоящему.
            PonyAction::ToggleSleep => {
                if pony_index >= self.ponies.len() { return; }
                let is_sleeping = matches!(self.ponies[pony_index].interaction_state, Some(InteractionState::Sleeping));
                if is_sleeping {
                    wake_up(&mut self.ponies[pony_index]);
                    println!("[Action] Wake up pony #{}", pony_index);
                } else {
                    enter_sleep(&mut self.ponies[pony_index], &mut self.loader);
                    println!("[Action] Sleep pony #{}", pony_index);
                }
            }
            // ДОБАВЛЕНО: усыпить/разбудить сразу всех пони. Если хотя бы
            // один сейчас не спит — усыпляем всех; если уже все спят —
            // будим всех (единая кнопка-переключатель, а не два отдельных
            // пункта меню).
            PonyAction::ToggleSleepAll => {
                let any_awake = self.ponies.iter()
                    .any(|p| !matches!(p.interaction_state, Some(InteractionState::Sleeping)));

                for i in 0..self.ponies.len() {
                    let is_sleeping = matches!(self.ponies[i].interaction_state, Some(InteractionState::Sleeping));
                    if any_awake && !is_sleeping {
                        enter_sleep(&mut self.ponies[i], &mut self.loader);
                    } else if !any_awake && is_sleeping {
                        wake_up(&mut self.ponies[i]);
                    }
                }
                println!("[Action] Sleep/Pause All → {}", if any_awake { "sleeping all" } else { "waking all" });
            }
            // ИЗМЕНЕНО: "Add Pony" теперь настоящее подменю (см.
            // ContextMenu::show_add_pony_list, обрабатывается отдельно в
            // window_event до попадания сюда) — можно выбрать конкретного
            // пони, а не только случайного. Оба варианта используют тот же
            // spawn_queue, которым пользуется главная панель (webview) —
            // заспавнится на следующем RedrawRequested.
            PonyAction::SpawnRandomPony => {
                let available: Vec<String> = self.loader.configs.iter().map(|c| c.name.clone()).collect();
                if available.is_empty() {
                    println!("[Action] Add Pony: no pony configs available");
                } else {
                    let idx = fastrand::usize(0..available.len());
                    let name = available[idx].clone();
                    println!("[Action] Add Pony (random) → {}", name);
                    self.spawn_queue.lock().unwrap().push(name);
                    let _ = self.proxy.send_event(UserEvent::RequestRedraw);
                }
            }
            PonyAction::SpawnNamedPony(name) => {
                println!("[Action] Add Pony → {}", name);
                self.spawn_queue.lock().unwrap().push(name);
                let _ = self.proxy.send_event(UserEvent::RequestRedraw);
            }
            // Обрабатываются напрямую в обработчике клика по меню (см.
            // window_event) до вызова execute_pony_action — сюда попасть
            // не должны, но матч обязан быть исчерпывающим.
            PonyAction::OpenAddPonyMenu | PonyAction::BackToMainMenu => {}
            // ДОБАВЛЕНО: возвращает/поднимает главную панель управления
            // (webview-окно со списком пони/мониторов), которая могла
            // оказаться скрытой за окнами пони.
            PonyAction::ReturnToMenu => {
                if let Some(w) = &self.ui_window {
                    w.set_visible(true);
                    w.focus_window();
                    println!("[Action] Return to Menu");
                }
            }
            // ДОБАВЛЕНО: полный выход из приложения — сохраняем настройки,
            // как и при закрытии главного окна (WindowEvent::CloseRequested).
            PonyAction::Exit => {
                println!("[Action] Exit");
                self.settings.save(&self.settings_path);
                event_loop.exit();
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
                            pony.animation_speed_mult = 1.0;
                        }
                    }
                    InteractionState::Fed { ref mut timer, original_speed_mult } => {
                        *timer -= dt;
                        if *timer <= 0.0 {
                            let mult = *original_speed_mult;
                            pony.vx /= mult;
                            pony.vy /= mult;
                            if let Some(orig_dur) = pony.original_frame_duration {
                                pony.animation.default_delay = orig_dur;
                                pony.original_frame_duration = None;
                            }
                            pony.animation_speed_mult = 1.0;
                            pony.interaction_state = None;
                        }
                    }
                    InteractionState::Petted { ref mut timer } => {
                        *timer -= dt;
                        if *timer <= 0.0 {
                            if let Some(orig_dur) = pony.original_frame_duration {
                                pony.animation.default_delay = orig_dur;
                                pony.original_frame_duration = None;
                            }
                            pony.behavior_timer = 0.0;
                            pony.animation_speed_mult = 1.0;
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
        // ИСПРАВЛЕНО: защита от деления на ноль/паники Duration::from_secs_f64,
        // если fps_limit когда-нибудь окажется равен 0 (например, из будущего
        // кода или повреждённого settings-файла).
        let frame_duration = std::time::Duration::from_secs_f64(1.0 / self.fps_limit.max(1) as f64);
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

        if let Some(surface) = &mut self.main_surface {
            if let Some(window) = &self.main_window {
                let size = window.inner_size();
                if let (Some(sw), Some(sh)) = (NonZeroU32::new(size.width), NonZeroU32::new(size.height)) {
                    surface.resize(sw, sh).unwrap();
                    let mut buffer = surface.buffer_mut().unwrap();
                    let bw = sw.get() as usize;
                    let bh = sh.get() as usize;
                    buffer.fill(0x00000000);

                    for p in &self.ponies {
                        if p.current_frame >= p.animation.frames.len() { continue; }
                        let frame = &p.animation.frames[p.current_frame].data;
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

        self.render_context_menu();

        self.frame_counter += 1;
        self.perf.update(self.ponies.len(), self.loader.sprite_cache.len());
        if self.frame_counter % 60 == 0 {
            println!("[Stats] {} | Windows: {}", self.perf.stats_string(), self.interaction_windows.len());
        }
    }
}

// ==================== UPDATE PONIES С НОВОЙ ЛОГИКОЙ АНИМАЦИИ ====================

// ИСПРАВЛЕНО (вся функция переписана): раньше выбор следующего поведения был
// собственным изобретением — 15%-й шанс "форсированной редкой" анимации
// (uniform-выбор среди ВСЕХ поведений, включая отключённые/недостижимые) плюс
// отдельный проход по вероятностям. Это не соответствовало оригиналу и на
// практике перекашивало распределение поведений: с одной стороны, поведения
// с маленьким Chance каждый пятый-шестой раз выбирались наравне с частыми
// (это и есть форс 15%), с другой — из-за раннего `break` при первом
// совпадении `rand_val <= 0.0` реальные веса не всегда соблюдались корректно.
// Пользователь просил свериться с оригиналом (Pony.vb) — там выбор поведения
// это Pony.GetCandidateBehavior(): равномерно-взвешенный случайный выбор по
// накопленной вероятности (Chance) среди ВСЕХ доступных поведений, без каких-
// либо искусственных "форсирований". Это и реализовано ниже в
// weighted_choose_behavior(), а сама функция module-level, чтобы её могли
// использовать все места выбора поведения (не только эта функция).
fn change_pony_behavior(pony: &mut Pony, loader: &mut DesktopPoniesLoader) {
    if pony.grabbed { return; }
    if pony.interaction_state.is_some() { return; }
    if pony.available_behaviors.is_empty() { return; }

    let old_behavior_name = pony.current_behavior.clone();

    // ДОБАВЛЕНО: это, вероятнее всего, ГЛАВНАЯ причина «не все анимации из
    // .ini проигрываются». Поле linked_behavior (LinkedBehavior в оригинале)
    // парсилось из .ini и даже редактировалось в редакторе, но во время
    // самой игры нигде не читалось — то есть цепочки поведений (например,
    // "сесть" → "сидит" → "встать", где промежуточные шаги специально
    // сделаны с Chance=0, чтобы их НИКОГДА не выбирал случайный выбор, а
    // только явный переход по цепочке) были полностью нерабочими: шаги с
    // Chance=0 не выбирались случайно (это правильно), но и по цепочке на
    // них никто не переходил (это баг) — то есть такие поведения не
    // проигрывались НИКОГДА. В оригинале (Pony.vb::StepOnce) при истечении
    // текущего поведения ПЕРВЫМ делом проверяется его LinkedBehavior — если
    // задан и найден среди доступных поведений, переход происходит на него
    // НАПРЯМУЮ, без какого-либо случайного выбора. Портируем это здесь же,
    // до вызова взвешенного случайного выбора.
    if let Some(linked) = find_linked_behavior(pony) {
        println!("[Behavior] {} → {} (linked from {})", pony.config_name, linked.name, old_behavior_name);
        apply_chosen_behavior(pony, loader, &linked);
        return;
    }

    let mut chosen = match weighted_choose_behavior(&pony.available_behaviors) {
        Some(b) => b,
        None => return,
    };

    let repeats_previous = chosen.name == old_behavior_name;
    if repeats_previous {
        pony.current_behavior_repeat_count += 1;
    } else {
        pony.current_behavior_repeat_count = 0;
    }

    // ДОБАВЛЕНО: у оригинала нет отдельного ограничения на повтор Stand-
    // анимаций — это не про верность Pony.vb, а самостоятельное требование:
    // Stand-анимации (имя содержит "stand", без учёта регистра) не должны
    // играться больше 2 раз ПОДРЯД. Считаем так: если это уже 3-й подряд
    // выбор того же Stand-поведения (current_behavior_repeat_count достиг 2
    // ПОСЛЕ инкремента выше, т.е. до этого оно уже отыграло 2 раза подряд),
    // принудительно выбираем что-то другое.
    let is_stand = chosen.name.to_lowercase().contains("stand");
    let stand_limit_hit = repeats_previous && is_stand && pony.current_behavior_repeat_count >= 2;

    // Поле do_not_repeat_animations (35-я колонка pony.ini) — отдельная,
    // общая для любых поведений настройка "не повторять этот же выбор
    // подряд вообще" (срабатывает сразу на первом повторе).
    let generic_no_repeat_hit = repeats_previous && chosen.do_not_repeat_animations && pony.current_behavior_repeat_count >= 1;

    if stand_limit_hit || generic_no_repeat_hit {
        if let Some(alt) = weighted_choose_behavior_excluding(&pony.available_behaviors, &old_behavior_name) {
            println!("[Behavior Limit] {} → {} (was {} x{}, {})",
                     pony.config_name, alt.name, old_behavior_name, pony.current_behavior_repeat_count,
                     if stand_limit_hit { "stand limit" } else { "do_not_repeat_animations" });
            chosen = alt;
            pony.current_behavior_repeat_count = 0;
        }
    }

    if chosen.probability < 0.01 {
        println!("[RARE!] {} → {} (prob: {})", pony.config_name, chosen.name, chosen.probability);
    } else {
        println!("[Behavior] {} → {} (prob: {})", pony.config_name, chosen.name, chosen.probability);
    }

    apply_chosen_behavior(pony, loader, &chosen);
}

/// Взвешенный случайный выбор поведения по накопленной вероятности (Chance) —
/// как в оригинале, Pony.vb::GetCandidateBehavior (упрощённая версия без
/// фильтрации по группе/достижимости цели, которых нет в этом порту).
fn weighted_choose_behavior(candidates: &[Behavior]) -> Option<Behavior> {
    if candidates.is_empty() {
        return None;
    }
    if candidates.len() == 1 {
        return Some(candidates[0].clone());
    }

    let total: f32 = candidates.iter().map(|b| b.probability).sum();
    if total <= 0.0 {
        // Если у всех Chance = 0 (некорректный .ini) — равномерный выбор,
        // чтобы поведение вообще могло смениться, а не "зависало" молча.
        let idx = fastrand::usize(0..candidates.len());
        return Some(candidates[idx].clone());
    }

    let random_choice = fastrand::f32() * total;
    let mut cumulative = 0.0;
    for b in candidates {
        cumulative += b.probability;
        if cumulative >= random_choice {
            return Some(b.clone());
        }
    }
    candidates.last().cloned()
}

/// Находит связанное поведение (LinkedBehavior) для ТЕКУЩЕГО поведения
/// пони, если оно задано в .ini — как Pony.vb::GetLinkedBehavior()
/// (поиск по имени без учёта регистра среди доступных поведений).
fn find_linked_behavior(pony: &Pony) -> Option<Behavior> {
    let current = pony.available_behaviors.iter().find(|b| b.name == pony.current_behavior)?;
    if current.linked_behavior.is_empty() {
        return None;
    }
    pony.available_behaviors.iter()
        .find(|b| b.name.eq_ignore_ascii_case(&current.linked_behavior))
        .cloned()
}

/// То же самое, но исключая поведение с указанным именем — используется для
/// принудительной смены при достижении лимита повторов.
fn weighted_choose_behavior_excluding(candidates: &[Behavior], exclude_name: &str) -> Option<Behavior> {
    let filtered: Vec<Behavior> = candidates.iter()
        .filter(|b| b.name != exclude_name)
        .cloned()
        .collect();
    weighted_choose_behavior(&filtered)
}

/// Загружает анимацию и применяет выбранное поведение к пони: спрайт, кадры,
/// таймер длительности, скорость и вектор движения. Вынесено в отдельную
/// функцию, потому что раньше этот блок был продублирован дословно в двух
/// местах (обычный выбор и форсированная редкая анимация) — после отказа от
/// форсирования путь выбора остался один, и дублирование ушло само собой.
fn apply_chosen_behavior(pony: &mut Pony, loader: &mut DesktopPoniesLoader, chosen: &Behavior) {
    let sprite_name = if !chosen.sprite_right.is_empty() {
        &chosen.sprite_right
    } else {
        &chosen.sprite_left
    };

    let animation = loader.load_pony_frames(&pony.config_name, sprite_name);
    let width = animation.width;
    let height = animation.height;

    pony.animation = animation;
    pony.width = width;
    pony.height = height;
    pony.current_frame = 0;
    pony.frame_timer = 0.0;
    pony.current_behavior = chosen.name.clone();
    pony.movement_type = MovementType::parse(&chosen.movement);
    pony.behavior_timer = chosen.min_duration + fastrand::f32() * (chosen.max_duration - chosen.min_duration);
    pony.animation_speed_mult = chosen.set_animation_speed.unwrap_or(1.0);
    pony.fixed_fps = chosen.set_fps;
    // ИСПРАВЛЕНО: это ГЛАВНАЯ причина «гифки зацикливаются, хотя в .ini
    // прописано, что цикличности быть не должно». Флаг "не зацикливать
    // кадры" в pony.ini — это поле prevent_loop (21-я колонка), отдельное от
    // do_not_repeat_animations (35-я колонка, про повтор ВЫБОРА поведения, а
    // не кадров внутри гифки). Раньше код брал значение из
    // do_not_repeat_animations, а реальный prevent_loop нигде не читался.
    pony.prevent_loop = chosen.prevent_loop;

    let speed = match pony.movement_type {
        MovementType::None | MovementType::Sleep => 0.0,
        _ => chosen.speed * 60.0,
    };

    let (vx, vy) = random_velocity_for_movement(&pony.movement_type, speed);
    pony.vx = vx;
    pony.vy = vy;
}

// ИСПРАВЛЕНО: раньше для ЛЮБОГО не-None/Sleep типа движения скорость
// направлялась под полностью случайным углом 0..360° (`fastrand::f32() *
// TAU`), а строго горизонтальные/вертикальные типы потом просто обнулялись
// постфактум в update_ponies(). В результате DiagonalOnly, DiagonalHorizontal,
// DiagonalVertical, HorizontalVertical и All визуально не отличались друг от
// друга — все двигались одинаково "по диагонали в любую сторону", то есть
// фактически не все виды движений из .ini реально проигрывались так, как
// задумано. В оригинале (Pony.vb::SetMovementWithoutDestination) для каждого
// типа сначала явно выбирается ОДНА из разрешённых составляющих (горизонталь/
// вертикаль/диагональ), и для диагонали диапазон угла зависит от того, какие
// именно составляющие разрешены. Портируем то же самое.
fn random_velocity_for_movement(movement_type: &MovementType, speed_px_per_sec: f32) -> (f32, f32) {
    if speed_px_per_sec <= 0.0 {
        return (0.0, 0.0);
    }

    let allow_h = matches!(movement_type,
        MovementType::HorizontalOnly | MovementType::HorizontalVertical |
        MovementType::DiagonalHorizontal | MovementType::All);
    let allow_v = matches!(movement_type,
        MovementType::VerticalOnly | MovementType::HorizontalVertical |
        MovementType::DiagonalVertical | MovementType::All);
    let allow_d = matches!(movement_type,
        MovementType::DiagonalOnly | MovementType::DiagonalHorizontal |
        MovementType::DiagonalVertical | MovementType::All);

    let mut options: Vec<u8> = Vec::with_capacity(3);
    if allow_h { options.push(0); }
    if allow_v { options.push(1); }
    if allow_d { options.push(2); }

    if options.is_empty() {
        return (0.0, 0.0);
    }

    let choice = options[fastrand::usize(0..options.len())];

    let (mut mx, mut my) = match choice {
        0 => (speed_px_per_sec, 0.0),
        1 => (0.0, speed_px_per_sec),
        _ => {
            // Диапазон угла зависит от ВСЕГО набора разрешённых составляющих
            // (как в оригинале), а не только от того, что выпало сейчас:
            // Diagonal+Vertical держится ближе к вертикали (15..45°),
            // Diagonal+Horizontal — ближе к горизонтали (105..135°), любой
            // другой набор с диагональю — широкий диапазон (15..75°).
            let angle_deg: f32 = if allow_v && !allow_h {
                fastrand::f32() * 30.0 + 15.0
            } else if allow_h && !allow_v {
                fastrand::f32() * 30.0 + 105.0
            } else {
                fastrand::f32() * 60.0 + 15.0
            };
            let angle = angle_deg.to_radians();
            (speed_px_per_sec * angle.sin(), speed_px_per_sec * angle.cos())
        }
    };

    if fastrand::bool() { mx = -mx; }
    if fastrand::bool() { my = -my; }

    (mx, my)
}

// ДОБАВЛЕНО: настоящий переход в сон — портирует идею _sleepBehavior из
// оригинала (Pony.vb): ищем поведение, у которого movement реально
// разобрался в MovementType::Sleep (т.е. в pony.ini явно задан
// "movement,...,Sleep,..."), и переключаемся на его спрайт/анимацию, как на
// любое обычное поведение. Раньше сон просто замораживал текущий кадр
// (animation_speed_mult = 0.0) — пони застывал статичной картинкой той
// анимации, что играла в момент клика, вместо того чтобы показать анимацию
// сна. Если в конфиге пони вообще нет поведения с movement = Sleep — берём
// любое стационарное (speed = 0) как разумный запасной вариант, чтобы пони
// хотя бы не продолжал бежать/лететь во сне.
fn enter_sleep(pony: &mut Pony, loader: &mut DesktopPoniesLoader) {
    pony.vx = 0.0;
    pony.vy = 0.0;
    pony.interaction_state = Some(InteractionState::Sleeping);
    pony.behavior_timer = 999999.0;

    let sleep_behavior = pony.available_behaviors.iter()
        .find(|b| MovementType::parse(&b.movement) == MovementType::Sleep)
        .or_else(|| pony.available_behaviors.iter().find(|b| b.speed <= 0.0))
        .cloned();

    if let Some(behavior) = sleep_behavior {
        let sprite_name = if !behavior.sprite_right.is_empty() {
            &behavior.sprite_right
        } else {
            &behavior.sprite_left
        };
        let animation = loader.load_pony_frames(&pony.config_name, sprite_name);
        pony.width = animation.width;
        pony.height = animation.height;
        pony.animation = animation;
        pony.current_frame = 0;
        pony.frame_timer = 0.0;
        pony.current_behavior = behavior.name.clone();
        pony.prevent_loop = behavior.prevent_loop;
        // Анимация сна должна реально проигрываться (мигание/дыхание и т.п.),
        // а не быть замороженной — используем собственную скорость поведения
        // из .ini, как и для любого другого поведения.
        pony.animation_speed_mult = behavior.set_animation_speed.unwrap_or(1.0);
        pony.fixed_fps = behavior.set_fps;
    } else {
        // Ни Sleep-, ни стационарного поведения не нашлось (маловероятно) —
        // хотя бы гарантируем, что пони не будет молча "бежать" во сне.
        pony.animation_speed_mult = pony.animation_speed_mult.max(0.1);
    }

    pony.movement_type = MovementType::Sleep;
}

/// Будит пони: сбрасывает состояние сна и обнуляет таймер поведения, чтобы
/// на следующем шаге update_ponies() пони как обычно выбрал новое поведение
/// через change_pony_behavior() — отдельно восстанавливать "то, что было до
/// сна" не требуется, ровно как и для пробуждения из mouseover/drag в
/// оригинале, когда нет более приоритетного состояния для восстановления.
fn wake_up(pony: &mut Pony) {
    pony.interaction_state = None;
    pony.movement_type = MovementType::None;
    pony.behavior_timer = 0.0;
    pony.animation_speed_mult = 1.0;
    pony.current_behavior_repeat_count = 0;
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

        // ИСПРАВЛЕННОЕ ОБНОВЛЕНИЕ АНИМАЦИИ
        let effective_dt = dt * p.animation_speed_mult;

        // Получаем задержку текущего кадра
        let current_delay = if p.current_frame < p.animation.frames.len() {
            p.animation.frames[p.current_frame].delay
        } else {
            p.animation.default_delay
        };

        p.frame_timer += effective_dt;

        // Переключение кадров
        while p.frame_timer >= current_delay && p.animation.frames.len() > 0 {
            p.frame_timer -= current_delay;
            p.current_frame += 1;

            if p.current_frame >= p.animation.frames.len() {
                if p.prevent_loop {
                    p.current_frame = p.animation.frames.len() - 1;
                    p.frame_timer = 0.0;
                    break;
                } else {
                    p.current_frame = 0;
                }
            }

            // Обновляем current_delay для следующей итерации
            let new_delay = if p.current_frame < p.animation.frames.len() {
                p.animation.frames[p.current_frame].delay
            } else {
                p.animation.default_delay
            };

            if p.frame_timer >= new_delay {
                continue;
            }
            break;
        }

        // Остальной код движения пони...
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
                p.animation_speed_mult = 1.0;

                if let Some(orig_dur) = p.original_frame_duration {
                    p.animation.default_delay = orig_dur;
                    p.original_frame_duration = None;
                }

                *grabbed_pony = None;
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
                    } else if body == "open_editor" {
                        launch_editor();
                    }
                })
                .build(&*ui_w)
                .unwrap();

            ui_w.set_visible(true);
            self.ui_window = Some(ui_w);
            self._webview = Some(wv);
        }

        if self.main_window.is_none() {
            self.create_main_window(event_loop);
        }
    }

    fn window_event(&mut self, event_loop: &winit::event_loop::ActiveEventLoop, window_id: WindowId, event: WindowEvent) {
        let ui_id = self.ui_window.as_ref().map(|w| w.id());
        let main_id = self.main_window.as_ref().map(|w| w.id());
        let menu_id = self.menu_window.as_ref().map(|mw| mw.window.id());
        let interaction_window_idx = self.get_interaction_window_id(window_id);

        match event {
            WindowEvent::CloseRequested if Some(window_id) == ui_id => {
                self.settings.save(&self.settings_path);
                event_loop.exit();
            }

            WindowEvent::CursorMoved { position, .. } if Some(window_id) == main_id => {
                self.mouse_x = position.x as f32;
                self.mouse_y = position.y as f32;
            }

            // ДОБАВЛЕНО: у меню теперь собственное окно-хитбокс, поэтому его
            // координаты мыши уже ЛОКАЛЬНЫЕ (0,0 — левый верхний угол меню) —
            // никакого пересчёта относительно главного окна не требуется.
            WindowEvent::CursorMoved { position, .. } if Some(window_id) == menu_id => {
                self.menu_mouse_x = position.x as f32;
                self.menu_mouse_y = position.y as f32;
            }

            // ИСПРАВЛЕНО: раньше клики по пунктам меню ловились отдельным
            // обработчиком на ГЛАВНОМ окне (с временным hit-test), потому что
            // меню рисовалось прямо на его поверхности. Теперь у меню
            // собственное окно (см. create_menu_window/MenuWindow) — клики
            // обрабатываются здесь с локальными координатами меню.
            WindowEvent::MouseInput { state, button, .. } if Some(window_id) == menu_id => {
                if state == ElementState::Pressed {
                    match button {
                        MouseButton::Left => {
                            if let Some(item_idx) = self.context_menu.hit_test(self.menu_mouse_x, self.menu_mouse_y) {
                                if let Some(action) = self.context_menu.get_action(item_idx) {
                                    // ДОБАВЛЕНО: переходы в подменю "Add Pony" и обратно
                                    // не должны закрывать меню — только пересобрать
                                    // список пунктов и подогнать размер окна под него.
                                    match action {
                                        PonyAction::OpenAddPonyMenu => {
                                            let names: Vec<String> = self.loader.configs.iter().map(|c| c.name.clone()).collect();
                                            self.context_menu.show_add_pony_list(&names);
                                            self.resize_menu_window_for_items();
                                        }
                                        PonyAction::BackToMainMenu => {
                                            let is_sleeping = self.context_menu.pony_index
                                                .and_then(|idx| self.ponies.get(idx))
                                                .map(|p| matches!(p.interaction_state, Some(InteractionState::Sleeping)))
                                                .unwrap_or(false);
                                            let all_sleeping = !self.ponies.is_empty()
                                                && self.ponies.iter().all(|p| matches!(p.interaction_state, Some(InteractionState::Sleeping)));
                                            self.context_menu.show_main_menu(is_sleeping, all_sleeping);
                                            self.resize_menu_window_for_items();
                                        }
                                        _ => {
                                            if let Some(menu_pony_idx) = self.context_menu.pony_index {
                                                self.execute_pony_action(menu_pony_idx, action, event_loop);
                                            }
                                            self.close_context_menu();
                                        }
                                    }
                                }
                            }
                        }
                        MouseButton::Right => {
                            self.close_context_menu();
                        }
                        _ => {}
                    }
                }
            }

            WindowEvent::MouseInput { state, button, .. } if interaction_window_idx.is_some() => {
                let pressed = state == ElementState::Pressed;
                let iw_idx = interaction_window_idx.unwrap();

                if let Some(pony_idx) = self.get_pony_under_mouse_in_window(iw_idx) {
                    println!("[Click] Window #{} on pony #{}: {:?} pressed={}",
                             iw_idx, pony_idx, button, pressed);
                    self.handle_click(pony_idx, button, pressed, event_loop);
                }
            }

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
                let to_spawn: Vec<String> = self.spawn_queue.lock().unwrap().drain(..).collect();
                for name in to_spawn {
                    self.spawn_pony(&name, event_loop);
                }

                self.render_all_windows();

                if let Some(w) = &self.main_window { w.request_redraw(); }
                for iw in &self.interaction_windows {
                    iw.window.request_redraw();
                }
                // ДОБАВЛЕНО: без этого окно меню отрисовалось бы один раз при
                // открытии и больше не обновлялось бы — например, подсветка
                // пункта при наведении мыши не отслеживалась бы в реальном
                // времени, как у остальных окон (главного и interaction-окон).
                if let Some(mw) = &self.menu_window { mw.window.request_redraw(); }
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

                self.interaction_windows.clear();
                self.main_window = None;
                self.main_surface = None;

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

// ==================== EDITOR MODE ====================

fn run_editor_mode() {
    use winit::event_loop::EventLoop;
    use winit::application::ApplicationHandler;
    use winit::event::WindowEvent;
    use winit::window::WindowAttributes;
    use winit::dpi::LogicalSize;
    use std::sync::Arc;
    use std::sync::Mutex;
    use crate::editor::EditorWindow;

    println!("🦄 Pony Editor v2.0");

    #[derive(Debug, Clone)]
    enum EditorEvent {}

    let event_loop = EventLoop::<EditorEvent>::with_user_event().build().unwrap();

    let loader = Arc::new(Mutex::new(DesktopPoniesLoader::new(".")));
    {
        let mut l = loader.lock().unwrap();
        if let Err(e) = l.load_all() {
            eprintln!("Warning: Could not load ponies: {}", e);
        }
        println!("Loaded {} ponies", l.configs.len());
    }

    let ponies_dir = std::env::current_dir().unwrap_or_default().join("Ponies");

    let attrs = WindowAttributes::default()
        .with_title("Pony Editor - Desktop Ponies")
        .with_inner_size(LogicalSize::new(1100, 750))
        .with_min_inner_size(LogicalSize::new(900, 600));

    let window = Arc::new(event_loop.create_window(attrs).unwrap());

    let editor_result = EditorWindow::from_window(window.clone(), loader, ponies_dir);

    struct EditorApp {
        editor: EditorWindow,
    }

    impl ApplicationHandler<EditorEvent> for EditorApp {
        fn resumed(&mut self, _event_loop: &winit::event_loop::ActiveEventLoop) {}

        fn window_event(&mut self, event_loop: &winit::event_loop::ActiveEventLoop, window_id: winit::window::WindowId, event: WindowEvent) {
            if self.editor.window.id() == window_id {
                match event {
                    WindowEvent::CloseRequested => event_loop.exit(),
                    WindowEvent::RedrawRequested => {
                        self.editor.process_messages();
                        self.editor.window.request_redraw();
                    }
                    _ => {}
                }
            }
        }
    }

    match editor_result {
        Ok(editor) => {
            println!("Editor ready!");
            let mut app = EditorApp { editor };
            event_loop.run_app(&mut app).unwrap();
        }
        Err(e) => {
            eprintln!("Failed to start editor: {}", e);
            std::process::exit(1);
        }
    }
}

// ==================== MAIN ====================

fn main() {
    let args: Vec<String> = std::env::args().collect();

    if args.iter().any(|arg| arg == "--editor" || arg == "-e") {
        run_editor_mode();
        return;
    }

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

    // ИСПРАВЛЕНО: fps_limit из сохранённых настроек раньше никогда не
    // применялся — App.fps_limit был всегда захардкожен в 60 независимо
    // от значения в desktop_ponies_settings.json.
    let initial_fps_limit = settings.fps_limit.clamp(10, 120);

    let mut monitor_manager = MonitorManager::new();
    monitor_manager.selected_ids = settings.selected_monitors.iter().cloned().collect();

    let el = EventLoop::<UserEvent>::with_user_event().build().unwrap();
    let proxy = el.create_proxy();

    let proxy_clone = proxy.clone();
    std::thread::spawn(move || {
        loop {
            std::thread::sleep(std::time::Duration::from_millis(16));
            let _ = proxy_clone.send_event(UserEvent::UpdateInteractionWindows);
        }
    });

    // ИСПРАВЛЕНО: spawn_on_start из настроек раньше нигде не читался — пони
    // из этого списка никогда не появлялись при запуске. Кладём их в
    // spawn_queue, который на первом RedrawRequested заспавнит ponies.
    if !settings.spawn_on_start.is_empty() {
        let mut q = spawn_q.lock().unwrap();
        for name in &settings.spawn_on_start {
            q.push(name.clone());
        }
    }

    el.run_app(&mut App {
        ponies: Vec::new(),
        main_window: None,
        main_surface: None,
        interaction_windows: Vec::new(),
        menu_window: None,
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
        menu_mouse_x: 0.0,
        menu_mouse_y: 0.0,
        perf: PerformanceMonitor::new(),
        frame_counter: 0,
        fps_limit: initial_fps_limit,
        frame_timer: Instant::now(),
        debug_hitboxes: true,
    }).unwrap();
}