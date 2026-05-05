// src_rust/window_manager.rs
use std::sync::Arc;
use std::path::Path;
use winit::window::{Window, WindowAttributes};
use winit::dpi::LogicalSize;
use crate::renderer::Renderer;
use crate::world::World;
use crate::pony::PonyEntity;
use glam::Vec2;
use winit::platform::windows::WindowAttributesExtWindows;

pub struct PonyWindow {
    pub window: Option<Arc<Window>>,
    pub renderer: Option<Renderer>,
    pub world: World,
    pub last_frame: Option<std::time::Instant>,
    pub initialized: bool,
}

impl PonyWindow {
    pub fn new() -> Self {
        Self {
            window: None,
            renderer: None,
            world: World::new(1920.0, 1080.0),
            last_frame: None,
            initialized: false,
        }
    }

    pub fn create_window(&mut self, event_loop: &winit::event_loop::ActiveEventLoop) {
        let monitor = event_loop.primary_monitor().unwrap();
        let size = monitor.size();
        self.world.screen_size = (size.width as f32, size.height as f32);

        let attributes = WindowAttributes::default()
            .with_title("Desktop Ponies Overlay")
            .with_decorations(false)
            .with_transparent(false)  // FALSE - Windows не поддерживает layered window с wgpu
            .with_inner_size(LogicalSize::new(size.width as f64, size.height as f64))
            .with_visible(false)
            .with_window_level(winit::window::WindowLevel::AlwaysOnTop)
            .with_skip_taskbar(true);

        let window = Arc::new(event_loop.create_window(attributes).unwrap());

        let mut renderer = pollster::block_on(Renderer::new(window.clone()));

        // Прозрачная fallback-текстура (RGBA 0,0,0,0)
        let transparent_png = create_transparent_png();
        renderer.texture_manager.load_texture(
            &renderer.device, &renderer.queue, "fallback", &transparent_png, 1,
        );

        self.window = Some(window);
        self.renderer = Some(renderer);
        self.last_frame = Some(std::time::Instant::now());
        self.initialized = true;
        println!("Pony window created {}x{}", size.width, size.height);
    }

    pub fn update_and_render(&mut self) {
        if !self.initialized { return; }
        if let (Some(renderer), Some(window)) = (&mut self.renderer, &self.window) {
            let now = std::time::Instant::now();
            let dt = self.last_frame.map(|f| (now - f).as_secs_f32().min(0.05)).unwrap_or(0.016);
            self.last_frame = Some(now);
            self.world.update(dt);

            let ponies: Vec<&PonyEntity> = self.world.ponies.values().collect();
            if !ponies.is_empty() {
                match renderer.render(&ponies) {
                    Ok(_) => {}
                    Err(wgpu::SurfaceError::Outdated) => {
                        let size = window.inner_size();
                        renderer.resize((size.width, size.height));
                    }
                    Err(wgpu::SurfaceError::Timeout) => {}
                    Err(e) => eprintln!("Render error: {:?}", e),
                }
            }
        }
    }

    pub fn spawn_pony(&mut self, name: &str) -> u64 {
        let id = self.world.next_id;
        self.world.next_id += 1;

        let (tex_id, frame_count, frame_duration) = load_pony_texture(
            &mut self.renderer, name,
        );

        let x = self.world.screen_size.0 / 2.0;
        let y = self.world.screen_size.1 / 2.0;

        let mut pony = PonyEntity::new_sprite(
            id, Vec2::new(x, y), tex_id,
            frame_count.max(1), frame_duration.max(0.1),
        );
        pony.velocity = Vec2::new(50.0, 0.0);

        self.world.ponies.insert(id, pony);
        println!("Spawned '{}' (id={}, tex={})", name, id, tex_id);
        id
    }
}

// ── Загрузка текстур ──────────────────────────────────────

fn load_pony_texture(
    renderer: &mut Option<Renderer>,
    pony_name: &str,
) -> (usize, u32, f32) {
    if let Some(ref mut r) = renderer {
        let pony_dir = Path::new("Ponies").join(pony_name);
        if !pony_dir.exists() {
            eprintln!("Pony dir not found: {:?}", pony_dir);
            return (0, 1, 0.1);
        }

        let mut image_paths: Vec<std::path::PathBuf> = Vec::new();
        collect_images(&pony_dir, &mut image_paths);

        for img_path in &image_paths {
            let ext = img_path
                .extension()
                .and_then(|e| e.to_str())
                .unwrap_or("")
                .to_lowercase();

            if let Ok(bytes) = std::fs::read(img_path) {
                if ext == "gif" {
                    if let Ok((atlas_data, frame_count, _, _, total_width, total_height, delays)) =
                        load_gif_frames(&bytes)
                    {
                        let avg_delay = if !delays.is_empty() {
                            delays.iter().sum::<f32>() / delays.len() as f32 / 1000.0
                        } else {
                            0.1
                        };
                        let tex_id = r.texture_manager.load_texture_raw(
                            &r.device, &r.queue, pony_name,
                            &atlas_data, total_width, total_height, frame_count,
                        );
                        println!("Loaded GIF for '{}': {} frames ({}x{} atlas, id={})",
                                 pony_name, frame_count, total_width, total_height, tex_id);
                        return (tex_id, frame_count, avg_delay.max(0.1));
                    }
                } else {
                    let tex_id = r.texture_manager.load_texture(
                        &r.device, &r.queue, pony_name, &bytes, 1,
                    );
                    println!("Loaded image for '{}': {} (id={})",
                             pony_name, img_path.display(), tex_id);
                    return (tex_id, 1, 0.1);
                }
            }
        }
    }
    (0, 1, 0.1)
}

fn load_gif_frames(
    data: &[u8],
) -> Result<(Vec<u8>, u32, u32, u32, u32, u32, Vec<f32>), String> {
    use std::io::Cursor;
    use image::AnimationDecoder;

    let cursor = Cursor::new(data);
    let decoder = image::codecs::gif::GifDecoder::new(cursor)
        .map_err(|e| format!("GIF decode error: {}", e))?;

    let mut all_frames: Vec<Vec<u8>> = Vec::new();
    let mut delays: Vec<f32> = Vec::new();
    let mut max_width = 0u32;
    let mut max_height = 0u32;

    let frames = decoder.into_frames();
    for frame_result in frames {
        match frame_result {
            Ok(frame) => {
                let buffer = frame.buffer();
                let rgba_vec = buffer.to_vec();
                let (delay_ms, _) = frame.delay().numer_denom_ms();
                delays.push(delay_ms as f32);
                all_frames.push(rgba_vec);
                max_width = max_width.max(buffer.width());
                max_height = max_height.max(buffer.height());
            }
            Err(e) => return Err(format!("GIF frame error: {:?}", e)),
        }
    }

    if all_frames.is_empty() {
        return Err("No frames in GIF".to_string());
    }

    let frame_count = all_frames.len() as u32;
    let total_width = max_width * frame_count;
    let total_height = max_height;
    let mut atlas = vec![0u8; (total_width * total_height * 4) as usize];

    for (i, frame_data) in all_frames.iter().enumerate() {
        let x_offset = (i as u32 * max_width) as usize;
        for y in 0..max_height as usize {
            let row_start_dst = y * total_width as usize * 4;
            let row_start_src = y * max_width as usize * 4;
            for x in 0..max_width as usize {
                let src_idx = row_start_src + x * 4;
                let dst_idx = row_start_dst + (x_offset + x) * 4;
                if src_idx + 3 < frame_data.len() && dst_idx + 3 < atlas.len() {
                    atlas[dst_idx] = frame_data[src_idx];
                    atlas[dst_idx + 1] = frame_data[src_idx + 1];
                    atlas[dst_idx + 2] = frame_data[src_idx + 2];
                    atlas[dst_idx + 3] = frame_data[src_idx + 3];
                }
            }
        }
    }

    Ok((atlas, frame_count, max_width, max_height, total_width, total_height, delays))
}

fn collect_images(dir: &Path, paths: &mut Vec<std::path::PathBuf>) {
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                collect_images(&path, paths);
            } else if let Some(ext) = path.extension() {
                let ext = ext.to_string_lossy().to_lowercase();
                if ext == "png" || ext == "gif" || ext == "bmp" || ext == "jpg" || ext == "jpeg" {
                    paths.push(path);
                }
            }
        }
    }
}

fn create_transparent_png() -> Vec<u8> {
    // PNG 4x4 полностью прозрачный
    use image::{RgbaImage, Rgba};
    let img = RgbaImage::from_pixel(4, 4, Rgba([0, 0, 0, 0]));
    let mut buf = std::io::Cursor::new(Vec::new());
    img.write_to(&mut buf, image::ImageFormat::Png).unwrap();
    buf.into_inner()
}
