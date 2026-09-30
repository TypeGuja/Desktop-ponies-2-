// src_rust/app.rs
//
// Оболочка приложения: прозрачное окно-оверлей поверх выбранных мониторов,
// ввод (курсор и кнопки читаются глобально — оверлей пропускает клики
// сквозь прозрачные места), перетаскивание пони/домов/эффектов, контекстное
// меню (как в оригинале: Remove / Sleep / Add Pony / Add House / Take Control /
// Show Options / Exit), звук, а также панель управления (WebView) и окно
// разговора с нейросетью.

use desktop_ponies_lib::ai_chat::{self, AiConfig, ChatMessage};
use desktop_ponies_lib::audio::Audio;
use desktop_ponies_lib::desktop::{self, Desktop};
use desktop_ponies_lib::luna::{self, FrameInput, Luna, LunaSettings, Spell};
use desktop_ponies_lib::loader::PonyCollection;
use desktop_ponies_lib::math::{RectI, V2};
use desktop_ponies_lib::menu::{Action, Click, Item, Menu};
use desktop_ponies_lib::model::*;
use desktop_ponies_lib::options::{Options, DEFAULT_PROFILE};
use desktop_ponies_lib::render::{self, SpriteCache};
use desktop_ponies_lib::ragdoll::{Anatomy, Ragdoll};
use desktop_ponies_lib::skel::{self, Motion, PuppetSet};
use desktop_ponies_lib::sim::{Context as SimContext, PonyId, World, STEP_SIZE};
use desktop_ponies_lib::text::{self, TextRenderer};
use desktop_ponies_lib::ui_state;
use desktop_ponies_lib::winapi::{self, MonitorInfo};
use serde_json::{json, Value};
use softbuffer::{Context, Surface};
use std::borrow::Cow;
use std::cell::RefCell;
use std::collections::HashMap;
use std::num::NonZeroU32;
use std::path::PathBuf;
use std::rc::Rc;
use std::sync::Arc;
use std::time::{Duration, Instant};
use winit::application::ApplicationHandler;
use winit::dpi::{LogicalSize, PhysicalPosition, PhysicalSize};
use winit::event::WindowEvent;
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoopProxy};
use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};
use winit::window::{Window, WindowAttributes, WindowId, WindowLevel};
use wry::WebViewBuilder;

#[derive(Debug, Clone)]
pub enum UserEvent {
    Ipc(String),
    AiReply { pony_id: PonyId, result: Result<String, String>, user_initiated: bool },
    ChatSubmit(String),
    ChatClose,
}

const UI_ORIGIN: &str = if cfg!(windows) { "http://dp.localhost/" } else { "dp://localhost/" };

type Surf = Surface<Arc<Window>, Arc<Window>>;

struct Overlay {
    window: Arc<Window>,
    surface: Surf,
    hwnd: isize,
    hittest: bool,
    visible: bool,
    on_top: bool,
    origin: (i32, i32),
    size: (u32, u32),
}

struct Panel {
    window: Arc<Window>,
    webview: wry::WebView,
}

struct ChatWindow {
    _webview: wry::WebView,
    window: Arc<Window>,
    pony_id: PonyId,
}

/// Кукла пони, которую схватили (или которая собирается обратно после отпускания).
struct RagState {
    rd: Ragdoll,
    /// Центр изображения на момент хвата (для связи с позицией пони в симуляции).
    center: V2,
}

#[derive(Clone, Copy, PartialEq, Debug)]
enum Hit {
    Pony(PonyId),
    House(u64),
    Effect(u64),
}

pub struct App {
    root: PathBuf,
    collection: PonyCollection,
    bases: Vec<Rc<PonyBase>>,
    house_bases: Vec<Rc<HouseBase>>,
    options: Options,
    world: World,
    monitors: Vec<MonitorInfo>,
    proxy: EventLoopProxy<UserEvent>,

    overlay: Option<Overlay>,
    panel: Option<Panel>,
    chat: Option<ChatWindow>,
    own_hwnds: Rc<RefCell<Vec<isize>>>,

    sprites: SpriteCache,
    text: Option<TextRenderer>,
    audio: Audio,

    start: Instant,
    next_frame: Instant,
    left_prev: bool,
    right_prev: bool,
    dragging: Option<Hit>,
    menu: Option<Menu>,
    manual: [Option<PonyId>; 2],
    all_sleeping: bool,
    fullscreen_hidden: bool,
    last_fullscreen_check: Instant,
    last_active_push: Instant,
    last_active_sig: String,
    was_empty: bool,

    ai_config: AiConfig,
    ai_config_path: PathBuf,
    ai_history: HashMap<PonyId, Vec<ChatMessage>>,
    ai_pending: std::collections::HashSet<PonyId>,
    spontaneous_timer: f64,
    /// Пони, которых надо запустить сразу (аргумент --spawn).
    pub autostart: Vec<String>,
    time_shift: f64,
    last_raw_ms: f64,
    last_sim_ms: f64,
    puppets: PuppetSet,
    last_draw_at: Instant,
    ragdolls: HashMap<PonyId, RagState>,
    last_rag_at: Instant,
    /// Магия Луны: окна, иконки, курсор.
    luna: Luna,
    desktop: Box<dyn Desktop>,
    last_luna_at: Instant,
}

// ------------------------------------------------------------------ helpers

pub fn find_root() -> PathBuf {
    let mut cands: Vec<PathBuf> = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        cands.push(cwd);
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            cands.push(dir.to_path_buf());
            if let Some(p) = dir.parent() {
                cands.push(p.to_path_buf());
                if let Some(pp) = p.parent() {
                    cands.push(pp.to_path_buf());
                }
            }
        }
    }
    cands.into_iter().find(|p| p.join("Ponies").is_dir()).unwrap_or_else(|| PathBuf::from("."))
}

fn mime_for(path: &str) -> &'static str {
    match path.rsplit('.').next().unwrap_or("").to_ascii_lowercase().as_str() {
        "gif" => "image/gif",
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "html" => "text/html; charset=utf-8",
        "css" => "text/css; charset=utf-8",
        "js" => "application/javascript; charset=utf-8",
        "mp3" => "audio/mpeg",
        _ => "application/octet-stream",
    }
}

fn hwnd_of(w: &Window) -> isize {
    match w.window_handle().map(|h| h.as_raw()) {
        Ok(RawWindowHandle::Win32(h)) => h.hwnd.get(),
        _ => 0,
    }
}

impl App {
    pub fn new(proxy: EventLoopProxy<UserEvent>) -> App {
        let root = find_root();
        println!("[App] Content root: {:?}", root);
        let profile = Options::current_profile_name(&root);
        let options = Options::load_profile(&root, &profile, false);
        let monitors = winapi::monitors();
        let collection = PonyCollection::load(&root, true);
        println!("[App] Loaded {} ponies and {} houses", collection.bases.len(), collection.houses.len());
        let ai_config_path = root.join("ai_config.json");
        let ai_config = AiConfig::load(&ai_config_path);

        let region = winapi::allowed_area(&monitors, &options.screens, options.allowed_region);
        let mut world = World::new(SimContext::new(region), None);
        let own_hwnds: Rc<RefCell<Vec<isize>>> = Rc::new(RefCell::new(Vec::new()));
        {
            let own = own_hwnds.clone();
            world.ctx.window_at_point = Some(Box::new(move |x, y| winapi::window_rect_at_point(x, y, &own.borrow())));
        }
        let mut app = App {
            root,
            collection: PonyCollection::empty(&PathBuf::from(".")),
            bases: Vec::new(),
            house_bases: Vec::new(),
            options,
            world,
            monitors,
            proxy,
            overlay: None,
            panel: None,
            chat: None,
            own_hwnds,
            sprites: SpriteCache::new(),
            text: TextRenderer::load(12.0),
            audio: Audio::new(),
            start: Instant::now(),
            next_frame: Instant::now(),
            left_prev: false,
            right_prev: false,
            dragging: None,
            menu: None,
            manual: [None, None],
            all_sleeping: false,
            fullscreen_hidden: false,
            last_fullscreen_check: Instant::now(),
            last_active_push: Instant::now(),
            last_active_sig: String::new(),
            was_empty: false,
            ai_config,
            ai_config_path,
            ai_history: HashMap::new(),
            ai_pending: Default::default(),
            spontaneous_timer: 60.0 + fastrand::f64() * 120.0,
            autostart: Vec::new(),
            time_shift: 0.0,
            last_raw_ms: 0.0,
            last_sim_ms: 0.0,
            puppets: PuppetSet::new(),
            last_draw_at: Instant::now(),
            ragdolls: HashMap::new(),
            last_rag_at: Instant::now(),
            luna: Luna::new(None),
            desktop: desktop::system(),
            last_luna_at: Instant::now(),
        };
        app.set_collection(collection);
        app.sync_context();
        app
    }

    fn set_collection(&mut self, c: PonyCollection) {
        self.bases = c.bases.iter().cloned().map(Rc::new).collect();
        self.house_bases = c.houses.iter().cloned().map(Rc::new).collect();
        self.world.all_bases = self.bases.clone();
        self.collection = c;
    }

    fn sync_context(&mut self) {
        let o = &self.options;
        let c = &mut self.world.ctx;
        c.effects_enabled = o.pony_effects_enabled;
        c.speech_enabled = o.pony_speech_enabled;
        c.interactions_enabled = o.pony_interactions_enabled;
        c.random_speech_chance = o.pony_speech_chance as f64;
        c.cursor_avoidance_enabled = o.cursor_avoidance_enabled;
        c.cursor_avoidance_radius = o.cursor_avoidance_size;
        c.dragging_enabled = o.pony_dragging_enabled;
        c.pony_avoidance_enabled = o.pony_avoids_ponies;
        c.window_avoidance_enabled = o.window_avoidance_enabled;
        c.stay_in_containing_window = o.window_containment;
        c.time_factor = o.time_factor as f64;
        c.scale_factor = o.scale_factor;
        c.exclusion_zone = o.exclusion_zone;
        c.teleportation_enabled = o.pony_teleport_enabled;
        c.region = winapi::allowed_area(&self.monitors, &o.screens, o.allowed_region);
        c.areas = winapi::allowed_areas(&self.monitors, &o.screens, o.allowed_region);
        c.dead_zones = winapi::dead_zones(c.region, &c.areas);
        self.world.max_pony_count = o.max_pony_count.max(0) as usize;
    }

    // ------------------------------------------------------------ windows

    fn create_overlay(&mut self, event_loop: &ActiveEventLoop) {
        let region = self.world.ctx.region;
        let mut attrs = WindowAttributes::default()
            .with_title("Desktop Ponies")
            .with_decorations(false)
            .with_transparent(true)
            .with_active(false)
            .with_inner_size(PhysicalSize::new(region.w.max(1) as u32, region.h.max(1) as u32))
            .with_position(PhysicalPosition::new(region.x, region.y))
            .with_window_level(if self.options.always_on_top { WindowLevel::AlwaysOnTop } else { WindowLevel::Normal });
        #[cfg(windows)]
        {
            use winit::platform::windows::WindowAttributesExtWindows;
            attrs = attrs.with_skip_taskbar(!self.options.show_in_taskbar);
        }
        let window = match event_loop.create_window(attrs) {
            Ok(w) => Arc::new(w),
            Err(e) => {
                eprintln!("[App] Cannot create overlay window: {}", e);
                return;
            }
        };
        let _ = window.set_cursor_hittest(false);
        let hwnd = hwnd_of(&window);
        self.own_hwnds.borrow_mut().push(hwnd);
        winapi::set_no_activate(hwnd);
        let ctx = Context::new(window.clone()).expect("softbuffer context");
        let surface = Surface::new(&ctx, window.clone()).expect("softbuffer surface");
        self.overlay = Some(Overlay {
            window,
            surface,
            hwnd,
            hittest: false,
            visible: true,
            on_top: self.options.always_on_top,
            origin: (region.x, region.y),
            size: (region.w.max(1) as u32, region.h.max(1) as u32),
        });
    }

    fn sync_overlay_geometry(&mut self) {
        let region = self.world.ctx.region;
        let Some(ov) = &mut self.overlay else { return };
        let want = (region.x, region.y);
        let size = (region.w.max(1) as u32, region.h.max(1) as u32);
        if ov.origin != want || ov.size != size {
            ov.window.set_outer_position(PhysicalPosition::new(want.0, want.1));
            let _ = ov.window.request_inner_size(PhysicalSize::new(size.0, size.1));
            ov.origin = want;
            ov.size = size;
        }
        if ov.on_top != self.options.always_on_top {
            ov.on_top = self.options.always_on_top;
            ov.window.set_window_level(if ov.on_top { WindowLevel::AlwaysOnTop } else { WindowLevel::Normal });
        }
    }

    fn create_panel(&mut self, event_loop: &ActiveEventLoop) {
        let attrs = WindowAttributes::default()
            .with_title("Desktop Ponies")
            .with_inner_size(LogicalSize::new(1000.0, 740.0))
            .with_min_inner_size(LogicalSize::new(720.0, 520.0));
        let window = match event_loop.create_window(attrs) {
            Ok(w) => Arc::new(w),
            Err(e) => {
                eprintln!("[App] Cannot create panel window: {}", e);
                return;
            }
        };
        self.own_hwnds.borrow_mut().push(hwnd_of(&window));
        let proxy = self.proxy.clone();
        let root = self.root.clone();
        let webview = WebViewBuilder::new()
            .with_custom_protocol("dp".to_string(), move |_id, req| serve_ui(&root, req.uri().path()))
            .with_ipc_handler(move |req| {
                let _ = proxy.send_event(UserEvent::Ipc(req.body().to_string()));
            })
            .with_url(format!("{}index.html", UI_ORIGIN))
            .build(&*window);
        match webview {
            Ok(webview) => {
                window.set_visible(true);
                self.panel = Some(Panel { window, webview });
            }
            Err(e) => eprintln!("[App] Cannot create panel webview: {}", e),
        }
    }

    fn show_panel(&mut self, tab: Option<&str>) {
        if let Some(p) = &self.panel {
            p.window.set_visible(true);
            p.window.focus_window();
        }
        if let Some(t) = tab {
            self.push(json!({"type": "tab", "name": t}));
        }
    }

    fn push(&self, v: Value) {
        if let Some(p) = &self.panel {
            let _ = p.webview.evaluate_script(&format!("window.dpReceive({})", v));
        }
    }

    fn push_state(&mut self) {
        let ai = json!({
            "base_url": self.ai_config.base_url,
            "model": self.ai_config.model,
            "language": self.ai_config.language,
            "spontaneous": self.ai_config.spontaneous,
            "has_key": self.ai_config.is_available(),
        });
        let profiles = Options::known_profiles(&self.root);
        let data = json!({
            "ponies": ui_state::ponies_json(&self.collection),
            "tags": ui_state::all_tags(&self.collection, &self.options.custom_tags),
            "custom_tags": self.options.custom_tags,
            "houses": ui_state::houses_json(&self.collection),
            "counts": self.options.pony_counts,
            "options": ui_state::options_to_json(&self.options),
            "profiles": profiles,
            "profile": self.options.profile_name,
            "monitors": ui_state::monitors_json(&self.monitors),
            "ai": ai,
            "origin": UI_ORIGIN,
            "version": "Desktop Ponies RS - Rust port of Desktop Ponies 1.69 with pony editor and AI dialogs",
        });
        self.push(json!({"type": "state", "data": data}));
        self.push_active(true);
    }

    fn active_json(&self) -> (Value, Value) {
        let list: Vec<Value> = self
            .world
            .ponies
            .iter()
            .map(|p| {
                json!({"id": p.id, "n": p.base.display_name, "b": p.current_behavior().name, "s": p.is_sleeping()})
            })
            .collect();
        let houses: Vec<Value> = self.world.houses.iter().map(|h| json!({"id": h.id, "n": h.base.name})).collect();
        (Value::Array(list), Value::Array(houses))
    }

    fn push_active(&mut self, force: bool) {
        let (list, houses) = self.active_json();
        let sig = format!("{}|{}", list, houses);
        if force || sig != self.last_active_sig {
            self.last_active_sig = sig;
            self.push(json!({"type": "active", "list": list, "houses": houses}));
        }
    }

    fn status(&self, text: &str) {
        self.push(json!({"type": "status", "text": text}));
    }

    // ------------------------------------------------------------ ponies

    fn add_pony_by_dir(&mut self, dir: &str) -> Option<PonyId> {
        if self.world.ponies.len() >= self.options.max_pony_count.max(0) as usize {
            self.status("Maximum number of ponies reached");
            return None;
        }
        let base = if dir == RANDOM_DIRECTORY {
            self.random_base()?
        } else {
            self.bases.iter().find(|b| ci_eq(&b.directory, dir))?.clone()
        };
        Some(self.world.add_pony(base))
    }

    fn random_base(&mut self) -> Option<Rc<PonyBase>> {
        if self.bases.is_empty() {
            return None;
        }
        if self.options.no_random_duplicates {
            let present: Vec<String> = self.world.ponies.iter().map(|p| p.base.directory.to_lowercase()).collect();
            let free: Vec<&Rc<PonyBase>> =
                self.bases.iter().filter(|b| !present.contains(&b.directory.to_lowercase())).collect();
            if !free.is_empty() {
                return Some(free[fastrand::usize(0..free.len())].clone());
            }
        }
        Some(self.bases[fastrand::usize(0..self.bases.len())].clone())
    }

    fn clear_world(&mut self) {
        let ids: Vec<PonyId> = self.world.ponies.iter().map(|p| p.id).collect();
        for id in ids {
            self.world.remove_pony(id);
        }
        let hs: Vec<u64> = self.world.houses.iter().map(|h| h.id).collect();
        for h in hs {
            self.world.remove_house(h);
        }
        let t = self.world.elapsed;
        self.world.update(t);
        self.manual = [None, None];
        self.ai_history.clear();
        self.ai_pending.clear();
        self.close_chat();
    }

    fn go(&mut self) {
        self.clear_world();
        self.sync_context();
        let counts: Vec<(String, i32)> = self.options.pony_counts.iter().map(|(k, v)| (k.clone(), *v)).collect();
        let mut n = 0;
        for (dir, count) in counts {
            for _ in 0..count.max(0) {
                if self.add_pony_by_dir(&dir).is_some() {
                    n += 1;
                }
            }
        }
        self.status(&format!("{} ponies started", n));
        if n > 0 {
            if let Some(p) = &self.panel {
                p.window.set_visible(false);
            }
        }
        self.push_active(true);
    }

    // ------------------------------------------------------------ IPC from panel

    fn handle_ipc(&mut self, event_loop: &ActiveEventLoop, body: &str) {
        let Ok(v) = serde_json::from_str::<Value>(body) else { return };
        let cmd = v["cmd"].as_str().unwrap_or("");
        match cmd {
            "ready" => self.push_state(),
            "set_count" => {
                let dir = v["dir"].as_str().unwrap_or("").to_string();
                let n = v["count"].as_i64().unwrap_or(0).clamp(0, 999) as i32;
                if n > 0 {
                    self.options.pony_counts.insert(dir, n);
                } else {
                    self.options.pony_counts.remove(&dir);
                }
            }
            "set_counts" => {
                if let Some(o) = v["counts"].as_object() {
                    self.options.pony_counts.clear();
                    for (k, n) in o {
                        let n = n.as_i64().unwrap_or(0).clamp(0, 999) as i32;
                        if n > 0 {
                            self.options.pony_counts.insert(k.clone(), n);
                        }
                    }
                }
            }
            "go" => self.go(),
            "spawn" => {
                if let Some(d) = v["dir"].as_str() {
                    self.add_pony_by_dir(d);
                    self.push_active(true);
                }
            }
            "remove" => {
                if let Some(id) = v["id"].as_u64() {
                    self.world.remove_pony(id);
                }
            }
            "remove_all" => {
                self.clear_world();
                self.push_active(true);
            }
            "sleep" => {
                if let Some(id) = v["id"].as_u64() {
                    if let Some(p) = self.world.pony_mut(id) {
                        p.sleep = !p.sleep;
                    }
                }
            }
            "sleep_all" => self.toggle_sleep_all(),
            "talk" => {
                if let Some(id) = v["id"].as_u64() {
                    self.open_chat(event_loop, id);
                }
            }
            "add_house" => {
                if let Some(i) = v["index"].as_u64() {
                    self.add_house(i as usize);
                }
            }
            "remove_house" => {
                if let Some(id) = v["id"].as_u64() {
                    self.world.remove_house(id);
                }
            }
            "options" => {
                ui_state::apply_options_json(&mut self.options, &v["data"]);
                self.sync_context();
                self.sync_overlay_geometry();
                if v["save"].as_bool().unwrap_or(false) {
                    let name = self.options.profile_name.clone();
                    self.save_profile(&name);
                }
            }
            "options_reset" => {
                let keep = (self.options.profile_name.clone(), self.options.pony_counts.clone(), self.options.custom_tags.clone());
                self.options = Options::default();
                self.options.profile_name = keep.0;
                self.options.pony_counts = keep.1;
                self.options.custom_tags = keep.2;
                self.sync_context();
                self.push_state();
            }
            "profile" => {
                let name = v["name"].as_str().unwrap_or("").to_string();
                match v["op"].as_str().unwrap_or("") {
                    "load" => {
                        self.options = Options::load_profile(&self.root, &name, true);
                        self.sync_context();
                        self.sync_overlay_geometry();
                        self.push_state();
                        self.status(&format!("Profile '{}' loaded", name));
                    }
                    "save" => {
                        self.save_profile(&name);
                        self.options.profile_name = name.clone();
                        let _ = std::fs::write(Options::profile_dir(&self.root).join("current.txt"), &name);
                        self.push_state();
                    }
                    "delete" => {
                        Options::delete_profile(&self.root, &name);
                        if self.options.profile_name == name {
                            self.options.profile_name = DEFAULT_PROFILE.to_string();
                        }
                        self.push_state();
                    }
                    _ => {}
                }
            }
            "tag_add" => {
                if let Some(t) = v["tag"].as_str() {
                    if !self.options.custom_tags.iter().any(|x| ci_eq(x, t)) {
                        self.options.custom_tags.push(t.to_string());
                    }
                    self.push_state();
                }
            }
            "tag_remove" => {
                if let Some(t) = v["tag"].as_str() {
                    self.options.custom_tags.retain(|x| !ci_eq(x, t));
                    self.push_state();
                }
            }
            "ai_save" => {
                let d = &v["data"];
                let mut cfg = self.ai_config.clone();
                if let Some(k) = d["api_key"].as_str() {
                    if !k.trim().is_empty() {
                        cfg.api_key = k.trim().to_string();
                    }
                }
                if let Some(s) = d["base_url"].as_str() {
                    if !s.trim().is_empty() {
                        cfg.base_url = s.trim().to_string();
                    }
                }
                if let Some(s) = d["model"].as_str() {
                    if !s.trim().is_empty() {
                        cfg.model = s.trim().to_string();
                    }
                }
                if let Some(s) = d["language"].as_str() {
                    cfg.language = s.to_string();
                }
                cfg.spontaneous = d["spontaneous"].as_bool().unwrap_or(cfg.spontaneous);
                cfg.save(&self.ai_config_path);
                self.ai_config = cfg;
                self.push_state();
            }
            "ai_clear" => {
                self.ai_config.api_key.clear();
                self.ai_config.save(&self.ai_config_path);
                self.close_chat();
                self.push_state();
            }
            "open_editor" => launch_editor(),
            "reload" => {
                let c = PonyCollection::load(&self.root, true);
                self.sprites.clear();
                self.set_collection(c);
                self.push_state();
                self.status("Pony collection reloaded");
            }
            "exit" => {
                self.save_current_state();
                event_loop.exit();
            }
            _ => {}
        }
    }

    fn save_profile(&mut self, name: &str) {
        match self.options.save_profile(&self.root, name) {
            Ok(_) => self.status(&format!("Profile '{}' saved", name)),
            Err(e) => self.status(&format!("Cannot save profile: {}", e)),
        }
    }

    /// Запоминает текущие настройки в текущем профиле (включая default) при выходе.
    fn save_current_state(&mut self) {
        let n = self.options.profile_name.clone();
        let _ = self.options.save_profile(&self.root, &n);
    }

    fn add_house(&mut self, index: usize) {
        if let Some(h) = self.house_bases.get(index).cloned() {
            self.world.add_house(h);
            self.push_active(true);
        }
    }

    fn toggle_sleep_all(&mut self) {
        self.all_sleeping = !self.all_sleeping;
        let v = self.all_sleeping;
        for p in &mut self.world.ponies {
            p.sleep = v;
        }
    }

    // ------------------------------------------------------------ menu

    fn pony_menu_items(&self, id: PonyId) -> Vec<Item> {
        let Some(p) = self.world.pony(id) else { return Vec::new() };
        let dir = p.base.directory.clone();
        let sleeping = p.sleep;
        let mut items: Vec<Item> = Vec::new();
        if self.ai_config.is_available() {
            items.push(Item::action(&format!("Talk to {}", p.base.display_name), Action::Talk(id)));
            items.push(Item::separator());
        }
        if luna::is_luna(p) {
            items.push(Item::action("Magic: Move a Window", Action::LunaMagic(id, 0)));
            items.push(Item::action("Magic: Move an Icon", Action::LunaMagic(id, 1)));
            items.push(Item::action("Magic: Carry a Pony", Action::LunaMagic(id, 7)));
            items.push(Item::action("Magic: Play a video", Action::LunaMagic(id, 2)));
            items.push(Item::action("Magic: Open Yandex Music", Action::LunaMagic(id, 3)));
            items.push(Item::action("Magic: Music Play/Pause", Action::LunaMagic(id, 4)));
            items.push(Item::action("Magic: Next track", Action::LunaMagic(id, 5)));
            items.push(Item::action("Magic: Previous track", Action::LunaMagic(id, 6)));
            items.push(Item::separator());
        }
        items.push(Item::action(&format!("Remove {}", dir), Action::RemovePony(id)));
        items.push(Item::action(&format!("Remove Every {}", dir), Action::RemoveEvery(dir.clone())));
        items.push(Item::separator());
        items.push(Item::action(if sleeping { "Wake up/Resume" } else { "Sleep/Pause" }, Action::ToggleSleep(id)));
        items.push(Item::action(if self.all_sleeping { "Wake up/Resume All" } else { "Sleep/Pause All" }, Action::ToggleSleepAll));
        items.push(Item::separator());
        items.push(Item::submenu("Add Pony", self.pony_selection_list()));
        items.push(Item::submenu("Add House", self.house_selection_list()));
        items.push(Item::separator());
        for (n, label) in [(1u8, "Player 1"), (2u8, "Player 2")] {
            let held = self.manual[(n - 1) as usize] == Some(id);
            items.push(Item::action(
                &format!("{} Control - {}", if held { "Release" } else { "Take" }, label),
                Action::TakeControl(id, n),
            ));
        }
        items.push(Item::separator());
        items.push(Item::action("Show Options", Action::ShowOptions));
        items.push(Item::action("Return To Menu", Action::ReturnToMenu));
        items.push(Item::action("Exit", Action::Exit));
        items
    }

    fn pony_selection_list(&self) -> Vec<Item> {
        let mut list = vec![Item::action(RANDOM_DIRECTORY, Action::AddRandomPony)];
        let mut tags: Vec<String> = STANDARD_TAGS.iter().map(|s| s.to_string()).collect();
        for t in &self.options.custom_tags {
            tags.push(t.clone());
        }
        for tag in tags {
            let ponies: Vec<Item> = self
                .bases
                .iter()
                .filter(|b| b.has_tag(&tag))
                .map(|b| Item::action(&b.directory, Action::AddPony(b.directory.clone())))
                .collect();
            if !ponies.is_empty() {
                list.push(Item::submenu(&tag, ponies));
            }
        }
        let untagged: Vec<Item> = self
            .bases
            .iter()
            .filter(|b| b.tags.is_empty())
            .map(|b| Item::action(&b.directory, Action::AddPony(b.directory.clone())))
            .collect();
        if !untagged.is_empty() {
            list.push(Item::submenu("[Not Tagged]", untagged));
        }
        list
    }

    fn house_selection_list(&self) -> Vec<Item> {
        if self.house_bases.is_empty() {
            return vec![Item::disabled("(no houses)")];
        }
        self.house_bases.iter().enumerate().map(|(i, h)| Item::action(&h.name, Action::AddHouse(i))).collect()
    }

    fn open_menu(&mut self, hit: Hit, cursor: (i32, i32)) {
        let items = match hit {
            Hit::Pony(id) => self.pony_menu_items(id),
            Hit::House(id) => {
                let name = self.world.houses.iter().find(|h| h.id == id).map(|h| h.base.name.clone()).unwrap_or_default();
                vec![Item::action(&format!("Remove {}", name), Action::RemoveHouse(id))]
            }
            Hit::Effect(_) => return,
        };
        if items.is_empty() {
            return;
        }
        let bounds = self.world.ctx.region;
        if let Some(tr) = self.text.as_mut() {
            self.menu = Some(Menu::open(items, cursor.0, cursor.1, bounds, tr));
        }
    }

    fn exec_action(&mut self, event_loop: &ActiveEventLoop, action: Action) {
        match action {
            Action::RemovePony(id) => self.world.remove_pony(id),
            Action::RemoveEvery(dir) => {
                let ids: Vec<PonyId> =
                    self.world.ponies.iter().filter(|p| ci_eq(&p.base.directory, &dir)).map(|p| p.id).collect();
                for id in ids {
                    self.world.remove_pony(id);
                }
            }
            Action::ToggleSleep(id) => {
                if let Some(p) = self.world.pony_mut(id) {
                    p.sleep = !p.sleep;
                }
            }
            Action::ToggleSleepAll => self.toggle_sleep_all(),
            Action::AddPony(dir) => {
                self.add_pony_by_dir(&dir);
            }
            Action::AddRandomPony => {
                self.add_pony_by_dir(RANDOM_DIRECTORY);
            }
            Action::AddHouse(i) => self.add_house(i),
            Action::RemoveHouse(id) => self.world.remove_house(id),
            Action::TakeControl(id, n) => {
                let slot = (n - 1) as usize;
                let other = 1 - slot;
                if self.manual[slot] == Some(id) {
                    self.release_control(slot);
                } else {
                    self.release_control(slot);
                    if self.manual[other] == Some(id) {
                        self.release_control(other);
                    }
                    self.manual[slot] = Some(id);
                }
            }
            Action::Talk(id) => self.open_chat(event_loop, id),
            Action::LunaMagic(id, kind) => {
                let own = self.own_hwnds.borrow().clone();
                let spell = match kind {
                    0 => Spell::Window,
                    1 => Spell::Icon,
                    2 => Spell::Video,
                    3 => Spell::Music,
                    4 => Spell::MusicPlayPause,
                    5 => Spell::MusicNext,
                    7 => Spell::Pony,
                    _ => Spell::MusicPrev,
                };
                self.luna.cast(&mut self.world, self.desktop.as_mut(), id, spell, &own);
            }
            Action::ShowOptions => self.show_panel(Some("options")),
            Action::ReturnToMenu => self.show_panel(Some("ponies")),
            Action::Exit => {
                self.save_current_state();
                event_loop.exit();
            }
        }
        self.push_active(false);
    }

    fn release_control(&mut self, slot: usize) {
        if let Some(id) = self.manual[slot].take() {
            if let Some(p) = self.world.pony_mut(id) {
                p.set_speed_override(None);
                p.destination_override = None;
            }
        }
    }

    // ------------------------------------------------------------ input

    fn manual_control(&mut self) {
        let keys: [[i32; 5]; 2] = [
            [winapi::VK_UP, winapi::VK_DOWN, winapi::VK_LEFT, winapi::VK_RIGHT, winapi::VK_SHIFT_R],
            [winapi::VK_W, winapi::VK_S, winapi::VK_A, winapi::VK_D, winapi::VK_SHIFT_L],
        ];
        for slot in 0..2 {
            let Some(id) = self.manual[slot] else { continue };
            let k = keys[slot];
            let mut mv = V2::ZERO;
            if winapi::key_down(k[0]) { mv.y -= 1.0; }
            if winapi::key_down(k[1]) { mv.y += 1.0; }
            if winapi::key_down(k[2]) { mv.x -= 1.0; }
            if winapi::key_down(k[3]) { mv.x += 1.0; }
            let boost = winapi::key_down(k[4]);
            let Some(p) = self.world.pony_mut(id) else {
                self.manual[slot] = None;
                continue;
            };
            let len = mv.length();
            if len > 0.0 {
                mv = mv / len;
                let speed = if boost { 200.0 } else { 100.0 };
                p.set_speed_override(Some(speed as f64));
                let loc = p.location();
                p.destination_override = Some(loc + mv * speed);
            } else {
                p.set_speed_override(Some(0.0));
                let loc = p.location();
                p.destination_override = Some(loc);
            }
        }
    }

    /// Что находится под курсором (по непрозрачным пикселям).
    fn hit_test(&mut self, cursor: (i32, i32)) -> Option<Hit> {
        let scale = self.world.ctx.scale_factor;
        // Пони: верхние (с большим bottom) — первыми.
        let mut order: Vec<(i32, PonyId)> = self
            .world
            .ponies
            .iter()
            .filter(|p| !p.expired && p.region().contains_point(cursor.0, cursor.1))
            .map(|p| (p.region().bottom(), p.id))
            .collect();
        order.sort_by(|a, b| b.0.cmp(&a.0));
        for (_, id) in order {
            let (path, t, prevent, region) = {
                let p = self.world.pony(id).unwrap();
                (p.current_image().path.clone(), p.image_time_index(), p.prevent_animation_loop(), p.region())
            };
            if let Some(anim) = self.sprites.get(&path, scale) {
                let f = anim.frame_at(t, prevent);
                if render::pixel_opaque(f, anim.w as usize, anim.h as usize, cursor.0 - region.x, cursor.1 - region.y) {
                    return Some(Hit::Pony(id));
                }
            }
        }
        // Эффекты.
        let effs: Vec<(u64, String, f64, bool, RectI)> = self
            .world
            .effects
            .iter()
            .filter(|e| !e.expired && e.region(scale).contains_point(cursor.0, cursor.1))
            .map(|e| (e.id, e.image().path.clone(), e.image_time_index(), e.effect_base().do_not_repeat_image_animations, e.region(scale)))
            .collect();
        for (id, path, t, prevent, region) in effs.into_iter().rev() {
            if let Some(anim) = self.sprites.get(&path, scale) {
                let f = anim.frame_at(t, prevent);
                if render::pixel_opaque(f, anim.w as usize, anim.h as usize, cursor.0 - region.x, cursor.1 - region.y) {
                    return Some(Hit::Effect(id));
                }
            }
        }
        // Дома.
        let houses: Vec<(u64, String, RectI)> = self
            .world
            .houses
            .iter()
            .filter(|h| !h.expired && h.region(scale).contains_point(cursor.0, cursor.1))
            .map(|h| (h.id, h.base.image.path.clone(), h.region(scale)))
            .collect();
        for (id, path, region) in houses.into_iter().rev() {
            if let Some(anim) = self.sprites.get(&path, scale) {
                let f = anim.frame_at(0.0, false);
                if render::pixel_opaque(f, anim.w as usize, anim.h as usize, cursor.0 - region.x, cursor.1 - region.y) {
                    return Some(Hit::House(id));
                }
            }
        }
        None
    }

    /// Пробует превратить схваченную пони в куклу: кадр режется на детали, и
    /// та деталь, за которую взяли, следует за курсором, а остальные — за ней.
    fn ragdoll_for(&mut self, id: PonyId, cursor: (i32, i32)) -> Option<RagState> {
        if !self.options.skeletal_animation {
            return None;
        }
        let scale = self.world.ctx.scale_factor;
        let (dir, beh_name, img_path, file, t, prevent, region, facing_right, center) = {
            let p = self.world.pony(id)?;
            let img = p.current_image();
            (
                p.base.directory.clone(),
                p.base.behaviors[p.image_behavior_index()].name.clone(),
                img.path.clone(),
                img.file_name(),
                p.image_time_index(),
                p.prevent_animation_loop(),
                p.region(),
                p.facing_right(),
                img.center() * scale,
            )
        };
        let spec = skel::rig_for(&dir)?;
        if !spec.allows(&beh_name, &file) {
            return None;
        }
        let anim = self.sprites.get(&img_path, scale)?;
        let frame = anim.frame_at(t, prevent);
        let anat = if facing_right { Anatomy::default_pony() } else { Anatomy::default_pony().mirrored() };
        let origin = V2::new(region.x as f32, region.y as f32);
        let mut rd = Ragdoll::new(&frame.pixels, anim.w as usize, anim.h as usize, &anat, origin)?;
        let (fx, fy) = (cursor.0 - region.x, cursor.1 - region.y);
        let part = rd.part_at(fx, fy)?;
        rd.grab(part, fx as f32, fy as f32, V2::new(cursor.0 as f32, cursor.1 as f32));
        Some(RagState { rd, center })
    }

    /// Физика кукол. Возвращает положение курсора для симуляции: пока пони
    /// схвачена, её позиция в симуляции следует за корпусом куклы.
    fn update_ragdolls(&mut self, cursor: (i32, i32), dt: f32) -> Option<(i32, i32)> {
        let mut cursor_override = None;
        let ids: Vec<PonyId> = self.ragdolls.keys().copied().collect();
        for id in ids {
            let loc = self.world.pony(id).map(|p| p.location());
            let Some(st) = self.ragdolls.get_mut(&id) else { continue };
            let Some(loc) = loc else {
                self.ragdolls.remove(&id);
                continue;
            };
            st.rd.set_home(loc - st.center);
            st.rd.update(dt, V2::new(cursor.0 as f32, cursor.1 as f32));
            if st.rd.is_grabbed() {
                let want = st.rd.origin_now() + st.center;
                cursor_override = Some((want.x.round() as i32, want.y.round() as i32));
            }
            if st.rd.done {
                self.ragdolls.remove(&id);
            }
        }
        cursor_override
    }

    fn set_drag(&mut self, hit: Hit, on: bool) {
        match hit {
            Hit::Pony(id) => {
                if let Some(p) = self.world.pony_mut(id) {
                    p.drag = on;
                }
            }
            Hit::House(id) => {
                if let Some(h) = self.world.houses.iter_mut().find(|h| h.id == id) {
                    h.drag = on;
                }
            }
            Hit::Effect(id) => {
                if let Some(e) = self.world.effects.iter_mut().find(|e| e.id == id) {
                    e.being_dragged = on;
                }
            }
        }
    }

    fn follow_drag_for_houses(&mut self, cursor: (i32, i32)) {
        let scale = self.world.ctx.scale_factor;
        for h in &mut self.world.houses {
            if h.drag {
                let r = h.region(scale);
                h.top_left = (cursor.0 - r.w / 2, cursor.1 - r.h / 2);
            }
        }
    }

    // ------------------------------------------------------------ frame

    /// Интервал между кадрами по настройке "Frame rate limit".
    fn frame_interval(&self) -> Duration {
        Duration::from_secs_f64(1.0 / self.options.fps_limit.max(1) as f64)
    }

    fn frame(&mut self, event_loop: &ActiveEventLoop) {
        let raw_ms = self.start.elapsed().as_secs_f64() * 1000.0;
        // Если кадры долго не шли (пони были скрыты, ПК спал), время симуляции
        // не должно "прыгать" — иначе она бы разом отыгрывала тысячи шагов.
        if raw_ms - self.last_raw_ms > 500.0 {
            self.time_shift += raw_ms - self.last_raw_ms - STEP_SIZE;
        }
        self.last_raw_ms = raw_ms;
        let now_ms = raw_ms - self.time_shift;

        // Полноэкранное приложение: прячем пони.
        if self.options.suspend_for_fullscreen_application && self.last_fullscreen_check.elapsed() > Duration::from_millis(700) {
            self.last_fullscreen_check = Instant::now();
            let own = self.own_hwnds.borrow().clone();
            let fs = winapi::fullscreen_app_active(&own, &self.monitors);
            if fs != self.fullscreen_hidden {
                self.fullscreen_hidden = fs;
                if let Some(ov) = &mut self.overlay {
                    ov.window.set_visible(!fs);
                    ov.visible = !fs;
                }
            }
        }
        if self.fullscreen_hidden {
            // Пока пони скрыты — время симуляции стоит на месте.
            self.time_shift = raw_ms - self.last_sim_ms;
            return;
        }
        self.last_sim_ms = now_ms;

        let cursor = winapi::cursor_pos();
        let left = winapi::key_down(winapi::VK_LBUTTON);
        let right = winapi::key_down(winapi::VK_RBUTTON);
        let left_edge = left && !self.left_prev;
        let right_edge = right && !self.right_prev;
        let left_release = !left && self.left_prev;
        self.left_prev = left;
        self.right_prev = right;

        self.sync_context();
        self.world.ctx.cursor = cursor;
        self.manual_control();

        let hit = if self.menu.is_some() { None } else { self.hit_test(cursor) };

        // ---- меню
        let mut action: Option<Action> = None;
        let mut close_menu = false;
        if let (Some(menu), Some(tr)) = (self.menu.as_mut(), self.text.as_mut()) {
            menu.hover(cursor.0, cursor.1, tr);
            if left_edge || right_edge {
                match menu.click(cursor.0, cursor.1) {
                    Click::Outside => close_menu = true,
                    Click::Action(a) if left_edge => {
                        action = Some(a);
                        close_menu = true;
                    }
                    _ => {}
                }
            }
        }
        if close_menu {
            self.menu = None;
        }
        if let Some(a) = action {
            self.exec_action(event_loop, a);
        }

        // ---- перетаскивание и контекстное меню
        if self.menu.is_none() && !close_menu {
            if left_edge {
                if let Some(h) = hit {
                    self.dragging = Some(h);
                    self.set_drag(h, true);
                    if let Hit::Pony(id) = h {
                        if let Some(st) = self.ragdoll_for(id, cursor) {
                            self.ragdolls.insert(id, st);
                        }
                    }
                }
            }
            if right_edge {
                if let Some(h) = hit {
                    self.open_menu(h, cursor);
                }
            }
        }
        if left_release {
            if let Some(h) = self.dragging.take() {
                self.set_drag(h, false);
                if let Hit::Pony(id) = h {
                    if let Some(st) = self.ragdolls.get_mut(&id) {
                        st.rd.release();
                    }
                }
            }
        }
        self.follow_drag_for_houses(cursor);

        // ---- ИИ: спонтанные реплики
        self.update_ai(now_ms);

        // ---- магия Луны (до симуляции: её цели пони получают на этом же шаге)
        self.update_luna(cursor, left || right);

        // ---- куклы: схваченная пони ведётся корпусом куклы, а не курсором напрямую
        let rag_dt = self.last_rag_at.elapsed().as_secs_f32();
        self.last_rag_at = Instant::now();
        let cursor_override = self.update_ragdolls(cursor, rag_dt);

        // ---- симуляция
        if let Some(o) = cursor_override {
            self.world.ctx.cursor = o;
        }
        self.world.update(now_ms);
        self.world.ctx.cursor = cursor;
        self.play_sounds();

        // ---- окно: прозрачность для кликов
        let over = self.menu.is_some() || hit.is_some() || self.dragging.is_some();
        if let Some(ov) = &mut self.overlay {
            if ov.hittest != over {
                let _ = ov.window.set_cursor_hittest(over);
                ov.hittest = over;
            }
        }

        self.sync_overlay_geometry();
        self.draw(cursor);

        if self.last_active_push.elapsed() > Duration::from_millis(800) {
            self.last_active_push = Instant::now();
            self.push_active(false);
        }
    }

    fn update_luna(&mut self, cursor: (i32, i32), buttons: bool) {
        let dt = self.last_luna_at.elapsed().as_secs_f32();
        self.last_luna_at = Instant::now();
        let own = self.own_hwnds.borrow().clone();
        let manual: Vec<PonyId> = self.manual.iter().flatten().copied().collect();
        let input = FrameInput {
            cursor,
            buttons,
            blocked: self.menu.is_some() || self.dragging.is_some(),
            manual: &manual,
            own_hwnds: &own,
        };
        let o = &self.options;
        let settings = LunaSettings {
            move_windows: o.luna_moves_windows,
            move_icons: o.luna_moves_icons,
            sleep_by_cursor: o.luna_sleeps_by_cursor,
            music: o.luna_music,
            move_ponies: o.luna_moves_ponies,
            cursor_idle_secs: o.luna_cursor_idle_secs as f32,
        };
        self.luna.update(&mut self.world, self.desktop.as_mut(), &input, &settings, dt);
    }

    fn play_sounds(&mut self) {
        let volume = self.options.sound_volume;
        let single = self.options.sound_single_channel_only;
        let enabled = self.options.sound_enabled;
        let mut to_play: Vec<(u64, String)> = Vec::new();
        for p in &mut self.world.ponies {
            if let Some(s) = p.take_speech_sound() {
                to_play.push((p.id, s));
            }
        }
        if enabled {
            for (id, path) in to_play {
                self.audio.play(id, &path, volume, single);
            }
        }
        self.audio.cleanup();
    }

    fn draw(&mut self, cursor: (i32, i32)) {
        let scale = self.world.ctx.scale_factor;
        let empty = self.world.ponies.is_empty() && self.world.houses.is_empty() && self.world.effects.is_empty() && self.menu.is_none();
        if empty && self.was_empty {
            return;
        }
        self.was_empty = empty;
        let Some(ov) = &mut self.overlay else { return };
        if !ov.visible {
            return;
        }
        let (w, h) = ov.size;
        let (Some(nw), Some(nh)) = (NonZeroU32::new(w), NonZeroU32::new(h)) else { return };
        if ov.surface.resize(nw, nh).is_err() {
            return;
        }
        let Ok(mut buffer) = ov.surface.buffer_mut() else { return };
        buffer.fill(0);
        let (bw, bh) = (w as usize, h as usize);
        let (ox, oy) = ov.origin;
        let draw_dt = self.last_draw_at.elapsed().as_secs_f32();
        self.last_draw_at = Instant::now();
        let rig_clock = Instant::now();
        let menu_open = self.menu.is_some();
        let time_factor = self.world.ctx.time_factor;
        let alive: Vec<u64> = self.world.ponies.iter().map(|p| p.id).collect();
        self.puppets.retain(&alive);

        // Дома — под всем остальным.
        for hs in &self.world.houses {
            if let Some(a) = self.sprites.get(&hs.base.image.path, scale) {
                let f = a.frame_at(0.0, false);
                render::blit(&mut buffer, bw, bh, f, a.w as usize, a.h as usize, hs.top_left.0 - ox, hs.top_left.1 - oy);
            }
        }

        // Пони и эффекты, отсортированные по нижней границе (ZOrderer).
        enum Sp<'a> {
            Pony(&'a desktop_ponies_lib::sim::Pony),
            Effect(&'a desktop_ponies_lib::sim::Effect),
        }
        let mut list: Vec<(i32, Sp)> = Vec::new();
        for p in &self.world.ponies {
            list.push((p.region().bottom(), Sp::Pony(p)));
        }
        for e in &self.world.effects {
            if !e.expired {
                list.push((e.region(scale).bottom(), Sp::Effect(e)));
            }
        }
        list.sort_by_key(|(b, _)| *b);
        for (_, sp) in &list {
            match sp {
                Sp::Pony(p) => {
                    let mut r = p.region();
                    // Схваченная пони в симуляции обновляется только раз в шаг
                    // (25 Гц) — рисуем её сразу под текущим курсором, чтобы
                    // перетаскивание не отставало и было плавным на любом FPS.
                    // Кукла (ragdoll) рисуется своей физикой каждый кадр.
                    let off = if p.is_dragging() && !self.ragdolls.contains_key(&p.id) {
                        let loc = p.location();
                        V2::new(cursor.0 as f32 - loc.x, cursor.1 as f32 - loc.y)
                    } else if let Some(to) = p.carry.filter(|_| p.is_carried()) {
                        // пони в магии Луны — так же рисуем там, где она сейчас, а не где была на шаге
                        to - p.location()
                    } else {
                        p.render_offset(self.last_sim_ms, time_factor)
                    };
                    r.x += off.x.round() as i32;
                    r.y += off.y.round() as i32;
                    if let Some(a) = self.sprites.get(&p.current_image().path, scale) {
                        let f = a.frame_at(p.image_time_index(), p.prevent_animation_loop());
                        let mut drawn = false;
                        // Схваченная (или собирающаяся обратно) пони — кукла из деталей.
                        if let Some(st) = self.ragdolls.get(&p.id) {
                            let (px, x, y, cw, ch) = st.rd.render();
                            let tmp = render::Frame { pixels: px, delay_ms: 0 };
                            render::blit(&mut buffer, bw, bh, &tmp, cw, ch, x - ox, y - oy);
                            drawn = true;
                        }
                        // Скелетная анимация: голова следит за курсором, хвост и грива
                        // качаются по физике. Ограничение по времени кадра — чтобы
                        // сотня пони не тормозила отрисовку.
                        if !drawn && self.options.skeletal_animation && rig_clock.elapsed() < Duration::from_millis(14) {
                            if let Some(spec) = skel::rig_for(&p.base.directory) {
                                let beh_name = &p.base.behaviors[p.image_behavior_index()].name;
                                if spec.allows(beh_name, &p.current_image().file_name()) {
                                    let mv = p.movement();
                                    let cx = (r.x + r.w / 2) as f32;
                                    let cy = (r.y + r.h / 2) as f32;
                                    let motion = Motion {
                                        vx: mv.x * 25.0,
                                        vy: mv.y * 25.0,
                                        facing_right: p.facing_right(),
                                        dragged: p.drag || p.is_carried(),
                                        cursor_rel: if menu_open { None } else { Some((cursor.0 as f32 - cx, cursor.1 as f32 - cy)) },
                                        sleeping: p.is_sleeping(),
                                    };
                                    let pup = self.puppets.get(p.id);
                                    pup.update(draw_dt, &motion);
                                    let pose = pup.pose;
                                    if let Some((px, ow, oh)) =
                                        skel::deform(&f.pixels, a.w as usize, a.h as usize, &spec, &pose, !p.facing_right())
                                    {
                                        let tmp = render::Frame { pixels: px, delay_ms: 0 };
                                        render::blit(
                                            &mut buffer, bw, bh, &tmp, ow, oh,
                                            r.x - skel::PAD as i32 - ox, r.y - skel::PAD as i32 - oy,
                                        );
                                        drawn = true;
                                    }
                                }
                            }
                        }
                        if !drawn {
                            render::blit(&mut buffer, bw, bh, f, a.w as usize, a.h as usize, r.x - ox, r.y - oy);
                        }
                    }
                }
                Sp::Effect(e) => {
                    if let Some(a) = self.sprites.get(&e.image().path, scale) {
                        let f = a.frame_at(e.image_time_index(), e.effect_base().do_not_repeat_image_animations);
                        render::blit(&mut buffer, bw, bh, f, a.w as usize, a.h as usize, e.top_left.0 - ox, e.top_left.1 - oy);
                    }
                }
            }
        }

        // Магия Луны — поверх пони, под репликами и меню.
        self.luna.draw(&mut buffer, bw, bh, (ox, oy));

        // Реплики и меню.
        if let Some(tr) = self.text.as_mut() {
            for p in &self.world.ponies {
                if let Some(t) = p.speech_text() {
                    let r = p.region();
                    text::draw_speech_bubble(&mut buffer, bw, bh, tr, t, r.x - ox, r.y - oy, r.w);
                }
            }
            if let Some(m) = &self.menu {
                m.draw(&mut buffer, bw, bh, (ox, oy), tr);
            }
        }
        let _ = cursor;
        let _ = buffer.present();
    }

    // ------------------------------------------------------------ AI

    fn ai_ready(&self) -> bool {
        self.ai_config.is_available()
    }

    fn update_ai(&mut self, now_ms: f64) {
        let _ = now_ms;
        self.spontaneous_timer -= self.frame_interval().as_secs_f64();
        if self.spontaneous_timer > 0.0 {
            return;
        }
        self.spontaneous_timer = 60.0 + fastrand::f64() * 120.0;
        if !self.ai_ready() || !self.ai_config.spontaneous || self.chat.is_some() || self.menu.is_some() {
            return;
        }
        let cands: Vec<PonyId> = self
            .world
            .ponies
            .iter()
            .filter(|p| !p.is_busy() && p.speech_text().is_none() && !self.ai_pending.contains(&p.id))
            .map(|p| p.id)
            .collect();
        if cands.is_empty() {
            return;
        }
        let id = cands[fastrand::usize(0..cands.len())];
        self.start_ai_request(id, None);
    }

    fn start_ai_request(&mut self, id: PonyId, user_text: Option<String>) {
        if !self.ai_ready() {
            return;
        }
        let Some(p) = self.world.pony(id) else { return };
        let name = p.base.display_name.clone();
        let categories = p.base.tags.clone();
        let mut others: Vec<String> = Vec::new();
        for o in &self.world.ponies {
            if o.id != id && !others.contains(&o.base.display_name) {
                others.push(o.base.display_name.clone());
            }
        }
        let system = ai_chat::build_system_prompt(&self.ai_config, &name, &categories, &others);
        let user_initiated = user_text.is_some();
        let hist = self.ai_history.entry(id).or_default();
        if let Some(t) = user_text {
            hist.push(ChatMessage { role: "user", content: t });
            let excess = hist.len().saturating_sub(ai_chat::MAX_HISTORY);
            if excess > 0 {
                hist.drain(..excess);
            }
        }
        let mut history = hist.clone();
        if !user_initiated {
            history.push(ChatMessage {
                role: "user",
                content: "(The user is silent right now. Say something short and spontaneous, in character - perhaps about another pony on the desktop or what you are doing.)".to_string(),
            });
        } else {
            self.world.say_custom(id, "...");
        }
        self.ai_pending.insert(id);
        let proxy = self.proxy.clone();
        ai_chat::request_async(self.ai_config.clone(), system, history, move |result| {
            let _ = proxy.send_event(UserEvent::AiReply { pony_id: id, result, user_initiated });
        });
    }

    fn handle_ai_reply(&mut self, id: PonyId, result: Result<String, String>, user_initiated: bool) {
        self.ai_pending.remove(&id);
        if self.world.pony(id).is_none() {
            return;
        }
        match result {
            Ok(text) => {
                if user_initiated {
                    self.ai_history.entry(id).or_default().push(ChatMessage { role: "assistant", content: text.clone() });
                }
                self.world.ctx.speech_enabled = true;
                self.world.say_custom(id, &text);
            }
            Err(e) => {
                eprintln!("[AI] Request failed: {}", e);
                if user_initiated {
                    if let Some(h) = self.ai_history.get_mut(&id) {
                        if matches!(h.last(), Some(m) if m.role == "user") {
                            h.pop();
                        }
                    }
                    let short: String = e.chars().take(100).collect();
                    self.world.say_custom(id, &format!("(AI error) {}", short));
                }
            }
        }
    }

    fn close_chat(&mut self) {
        if let Some(c) = self.chat.take() {
            c.window.set_visible(false);
        }
    }

    fn open_chat(&mut self, event_loop: &ActiveEventLoop, pony_id: PonyId) {
        self.close_chat();
        let Some(p) = self.world.pony(pony_id) else { return };
        let r = p.region();
        let name = p.base.display_name.clone();
        let attrs = WindowAttributes::default()
            .with_title("Pony Chat")
            .with_decorations(false)
            .with_inner_size(LogicalSize::new(360.0, 74.0))
            .with_position(PhysicalPosition::new(r.x, r.bottom() + 8))
            .with_window_level(WindowLevel::AlwaysOnTop);
        let Ok(window) = event_loop.create_window(attrs) else { return };
        let window = Arc::new(window);
        let proxy = self.proxy.clone();
        let html = chat_html(&name);
        match WebViewBuilder::new()
            .with_html(&html)
            .with_ipc_handler(move |req| {
                let body = req.body();
                if let Some(t) = body.strip_prefix("chat:") {
                    let _ = proxy.send_event(UserEvent::ChatSubmit(t.to_string()));
                } else if body == "chat_close" {
                    let _ = proxy.send_event(UserEvent::ChatClose);
                }
            })
            .build(&*window)
        {
            Ok(wv) => {
                window.focus_window();
                let _ = wv.focus();
                self.chat = Some(ChatWindow { _webview: wv, window, pony_id });
            }
            Err(e) => eprintln!("[Chat] {}", e),
        }
    }
}

// ------------------------------------------------------------------ misc

fn chat_html(name: &str) -> String {
    let safe = name.replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;").replace('"', "&quot;");
    r#"<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
html,body{margin:0;height:100%;background:#1e1e2e;color:#cdd6f4;font-family:Segoe UI,sans-serif;overflow:hidden}
.box{box-sizing:border-box;height:100%;padding:10px 12px;border:1px solid #6c7086;display:flex;flex-direction:column;gap:6px}
.title{font-size:12px;color:#a6adc8}
input{font-size:14px;padding:8px 10px;border-radius:6px;border:1px solid #45475a;background:#313244;color:#cdd6f4;outline:none}
input:focus{border-color:#cba6f7}
</style></head><body><div class="box">
<div class="title">Talk to __NAME__ &middot; Enter - send, Esc - close</div>
<input id="t" type="text" autocomplete="off" autofocus maxlength="500" placeholder="Say something...">
</div><script>
var t=document.getElementById('t');t.focus();
t.addEventListener('keydown',function(e){
  if(e.key==='Enter'&&t.value.trim()){window.ipc.postMessage('chat:'+t.value.trim());}
  else if(e.key==='Escape'){window.ipc.postMessage('chat_close');}
});
</script></body></html>"#
        .replace("__NAME__", &safe)
}

fn launch_editor() {
    if let Ok(exe) = std::env::current_exe() {
        match std::process::Command::new(exe).arg("--editor").spawn() {
            Ok(c) => println!("[Editor] started, pid {}", c.id()),
            Err(e) => eprintln!("[Editor] failed to start: {}", e),
        }
    }
}

/// Отдаёт интерфейс панели и файлы пони/домов для превью.
fn serve_ui(root: &std::path::Path, path: &str) -> wry::http::Response<Cow<'static, [u8]>> {
    let respond = |status: u16, mime: &str, body: Vec<u8>| {
        wry::http::Response::builder()
            .status(status)
            .header("Content-Type", mime)
            .header("Access-Control-Allow-Origin", "*")
            .body(Cow::Owned(body))
            .unwrap()
    };
    match path {
        "/" | "/index.html" => respond(200, mime_for("a.html"), include_str!("../src-ui/index.html").as_bytes().to_vec()),
        "/style.css" => respond(200, mime_for("a.css"), include_str!("../src-ui/style.css").as_bytes().to_vec()),
        "/app.js" => respond(200, mime_for("a.js"), include_str!("../src-ui/app.js").as_bytes().to_vec()),
        p if p.starts_with("/files/") => {
            let rel = urlencoding::decode(&p["/files/".len()..]).map(|c| c.to_string()).unwrap_or_default();
            let allowed = rel.starts_with("Ponies/") || rel.starts_with("Houses/");
            if !allowed || rel.contains("..") {
                return respond(403, "text/plain", b"forbidden".to_vec());
            }
            match std::fs::read(root.join(&rel)) {
                Ok(bytes) => respond(200, mime_for(&rel), bytes),
                Err(_) => respond(404, "text/plain", b"not found".to_vec()),
            }
        }
        _ => respond(404, "text/plain", b"not found".to_vec()),
    }
}

// ------------------------------------------------------------------ ApplicationHandler

impl ApplicationHandler<UserEvent> for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.overlay.is_none() {
            self.create_overlay(event_loop);
        }
        if self.panel.is_none() {
            self.create_panel(event_loop);
        }
        for name in std::mem::take(&mut self.autostart) {
            self.add_pony_by_dir(&name);
        }
        self.next_frame = Instant::now();
        event_loop.set_control_flow(ControlFlow::WaitUntil(self.next_frame));
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, window_id: WindowId, event: WindowEvent) {
        if let WindowEvent::CloseRequested = event {
            if self.panel.as_ref().map(|p| p.window.id()) == Some(window_id) {
                if self.world.ponies.is_empty() {
                    self.save_current_state();
                    event_loop.exit();
                } else if let Some(p) = &self.panel {
                    p.window.set_visible(false);
                }
            } else if self.chat.as_ref().map(|c| c.window.id()) == Some(window_id) {
                self.close_chat();
            }
        }
    }

    fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
        let now = Instant::now();
        if now >= self.next_frame {
            self.frame(event_loop);
            self.next_frame = Instant::now() + self.frame_interval();
        }
        event_loop.set_control_flow(ControlFlow::WaitUntil(self.next_frame));
    }

    fn user_event(&mut self, event_loop: &ActiveEventLoop, event: UserEvent) {
        match event {
            UserEvent::Ipc(body) => self.handle_ipc(event_loop, &body),
            UserEvent::AiReply { pony_id, result, user_initiated } => self.handle_ai_reply(pony_id, result, user_initiated),
            UserEvent::ChatSubmit(text) => {
                let id = self.chat.as_ref().map(|c| c.pony_id);
                self.close_chat();
                let text = text.trim().to_string();
                if let (Some(id), false) = (id, text.is_empty()) {
                    self.start_ai_request(id, Some(text));
                }
            }
            UserEvent::ChatClose => self.close_chat(),
        }
    }
}

#[allow(dead_code)]
fn _step() -> f64 {
    STEP_SIZE
}
