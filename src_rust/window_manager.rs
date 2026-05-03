// src_rust/window_manager.rs
use std::sync::Arc;
use std::path::Path;
use tao::window::Window;
use tao::dpi::LogicalSize;
use tao::platform::windows::WindowBuilderExtWindows;
use crate::renderer::Renderer;
use crate::world::World;
use crate::loader::DesktopPoniesLoader;
use crate::pony::PonyEntity;
use glam::Vec2;

pub struct PonyWindow {
    pub window: Option<Arc<Window>>,
    pub renderer: Option<Renderer>,
    pub world: World,
    pub loader: DesktopPoniesLoader,
    pub last_frame: Option<std::time::Instant>,
    pub initialized: bool,
}

impl PonyWindow {
    pub fn new() -> Self {
        let mut loader = DesktopPoniesLoader::new(".");
        let _ = loader.load_all();
        Self {
            window: None,
            renderer: None,
            world: World::new(1920.0, 1080.0),
            loader,
            last_frame: None,
            initialized: false,
        }
    }

    pub fn create_window(&mut self, event_loop: &tao::event_loop::EventLoop<()>) {
        let monitor = event_loop.available_monitors().next().unwrap();
        let size = monitor.size();

        let window = Arc::new(
            tao::window::WindowBuilder::new()
                .with_title("Desktop Ponies")
                .with_decorations(false)
                .with_transparent(true)
                .with_undecorated_shadow(false)
                .with_skip_taskbar(true)
                .with_inner_size(LogicalSize::new(size.width, size.height))
                .with_visible(false)
                .build(event_loop)
                .unwrap()
        );

        #[cfg(target_os = "windows")]
        unsafe {
            use tao::platform::windows::WindowExtWindows;
            use windows::Win32::UI::WindowsAndMessaging::{
                SetWindowLongPtrW, SetLayeredWindowAttributes,
                WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW,
                GWL_EXSTYLE, LWA_COLORKEY,
            };
            use windows::Win32::Foundation::HWND;

            let hwnd = HWND(window.hwnd() as *mut _);
            let ex_style = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW;
            SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex_style.0 as isize);
            SetLayeredWindowAttributes(hwnd, windows::Win32::Foundation::COLORREF(0), 0, LWA_COLORKEY);
            println!("Windows: black = transparent");
        }

        let mut renderer = pollster::block_on(Renderer::new(window.clone()));

        let white_png = create_white_png();
        renderer.texture_manager.load_texture(&renderer.device, &renderer.queue, "fallback", &white_png, 1);

        self.world.screen_size = (size.width as f32, size.height as f32);
        self.window = Some(window);
        self.renderer = Some(renderer);
        self.last_frame = Some(std::time::Instant::now());
        self.initialized = true;
    }

    pub fn update_and_render(&mut self) {
        if !self.initialized { return; }
        if let (Some(renderer), Some(_)) = (&mut self.renderer, &self.window) {
            let now = std::time::Instant::now();
            let dt = self.last_frame.map(|f| (now - f).as_secs_f32().min(0.05)).unwrap_or(0.016);
            self.last_frame = Some(now);
            self.world.update(dt);
            let ponies: Vec<&PonyEntity> = self.world.ponies.values().collect();
            if !ponies.is_empty() {
                let _ = renderer.render(&ponies);
            }
        }
    }

    pub fn spawn_pony(&mut self, name: &str) -> u64 {
        let id = self.world.next_id;
        self.world.next_id += 1;
        let config = self.loader.configs.iter().find(|c| c.name == name);
        let (tex_id, fc, fd) = if let Some(cfg) = config {
            load_pony_texture(&mut self.renderer, name, cfg)
        } else { (0usize, 1u32, 0.1f32) };

        let mut pony = PonyEntity::new_sprite(id, Vec2::new(self.world.screen_size.0/2.0, self.world.screen_size.1/2.0), tex_id, fc.max(1), fd.max(0.1));
        pony.velocity = Vec2::new(50.0, 0.0);
        self.world.ponies.insert(id, pony);
        id
    }
}

fn load_pony_texture(renderer: &mut Option<Renderer>, name: &str, _cfg: &crate::loader::PonyConfig) -> (usize, u32, f32) {
    if let Some(ref mut r) = renderer {
        let dir = Path::new("Ponies").join(name);
        let mut paths = Vec::new();
        collect_images(&dir, &mut paths);
        for p in &paths {
            if let Ok(bytes) = std::fs::read(p) {
                if p.extension().and_then(|e| e.to_str()) == Some("gif") {
                    if let Ok((atlas, fc, _, _, tw, th, delays)) = load_gif_frames(&bytes) {
                        let avg = delays.iter().sum::<f32>() / delays.len() as f32 / 1000.0;
                        let id = r.texture_manager.load_texture_raw(&r.device, &r.queue, name, &atlas, tw, th, fc);
                        return (id, fc, avg.max(0.1));
                    }
                } else {
                    let id = r.texture_manager.load_texture(&r.device, &r.queue, name, &bytes, 1);
                    return (id, 1, 0.1);
                }
            }
        }
    }
    (0, 1, 0.1)
}

fn load_gif_frames(data: &[u8]) -> Result<(Vec<u8>, u32, u32, u32, u32, u32, Vec<f32>), String> {
    use std::io::Cursor;
    use image::AnimationDecoder;
    let dec = image::codecs::gif::GifDecoder::new(Cursor::new(data)).map_err(|e| format!("{}", e))?;
    let mut frames = Vec::new();
    let mut delays = Vec::new();
    let mut mw = 0u32; let mut mh = 0u32;
    for f in dec.into_frames() {
        let f = f.map_err(|e| format!("{:?}", e))?;
        mw = mw.max(f.buffer().width()); mh = mh.max(f.buffer().height());
        let (d, _) = f.delay().numer_denom_ms();
        frames.push(f.buffer().to_vec()); delays.push(d as f32);
    }
    if frames.is_empty() { return Err("no frames".into()); }
    let fc = frames.len() as u32; let tw = mw * fc; let th = mh;
    let mut atlas = vec![0u8; (tw * th * 4) as usize];
    for (i, data) in frames.iter().enumerate() {
        let xo = (i as u32 * mw) as usize;
        for y in 0..mh as usize {
            let s = y * mw as usize * 4; let d = y * tw as usize * 4 + xo * 4;
            if d + mw as usize * 4 <= atlas.len() && s + mw as usize * 4 <= data.len() {
                atlas[d..d+mw as usize*4].copy_from_slice(&data[s..s+mw as usize*4]);
            }
        }
    }
    Ok((atlas, fc, mw, mh, tw, th, delays))
}

fn collect_images(dir: &Path, paths: &mut Vec<std::path::PathBuf>) {
    if let Ok(entries) = std::fs::read_dir(dir) {
        for e in entries.flatten() {
            let p = e.path();
            if p.is_dir() { collect_images(&p, paths); }
            else if let Some(ext) = p.extension().and_then(|e| e.to_str()) {
                if matches!(ext.to_lowercase().as_str(), "png"|"gif"|"bmp"|"jpg"|"jpeg") { paths.push(p); }
            }
        }
    }
}

fn create_white_png() -> Vec<u8> {
    vec![0x89,0x50,0x4E,0x47,0x0D,0x0A,0x1A,0x0A,0x00,0x00,0x00,0x0D,0x49,0x48,0x44,0x52,0x00,0x00,0x00,0x02,0x00,0x00,0x00,0x02,0x08,0x06,0x00,0x00,0x00,0x00,0x2E,0xBE,0x98,0x1B,0x00,0x00,0x00,0x14,0x49,0x44,0x41,0x54,0x78,0x9C,0x62,0x60,0x60,0x60,0xF8,0x0F,0x00,0x01,0x01,0x00,0x02,0x02,0x02,0xFE,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0x07,0x80,0x00,0x15,0x01,0x5D,0xB8,0xDA,0x22,0x00,0x00,0x00,0x00,0x49,0x45,0x4E,0x44,0xAE,0x42,0x60,0x82]
}