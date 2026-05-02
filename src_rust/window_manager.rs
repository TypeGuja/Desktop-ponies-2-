// src_rust/window_manager.rs
use std::sync::Arc;
use tao::window::Window;
use tao::dpi::LogicalSize;
use crate::renderer::Renderer;
use crate::world::World;
use crate::loader::DesktopPoniesLoader;
use crate::pony::PonyEntity;
use glam::Vec2;
use tao::platform::windows::WindowBuilderExtWindows;

pub struct PonyWindow {
    pub window: Option<Arc<Window>>,
    pub renderer: Option<Renderer>,
    pub world: World,
    pub loader: DesktopPoniesLoader,
    pub last_frame: Option<std::time::Instant>,
}

impl PonyWindow {
    pub fn new() -> Self {
        // НЕ загружаем пони повторно — они уже загружены в main
        let loader = DesktopPoniesLoader::new(".");
        Self {
            window: None,
            renderer: None,
            world: World::new(1920.0, 1080.0),
            loader,
            last_frame: None,
        }
    }

    pub fn create_window(&mut self, event_loop: &tao::event_loop::EventLoop<()>) {
        // Загружаем пони один раз здесь
        if let Err(e) = self.loader.load_all() {
            eprintln!("Loader warning: {}", e);
        }

        let monitor = event_loop.available_monitors().next()
            .expect("No monitor found!");
        let size = monitor.size();

        println!("PonyWindow: creating {}x{} window", size.width, size.height);

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

        let mut renderer = pollster::block_on(Renderer::new(window.clone()));

        let white_png = create_white_png();
        let tex_id = renderer.texture_manager.load_texture(
            &renderer.device, &renderer.queue, "fallback", &white_png, 1,
        );

        self.world.screen_size = (size.width as f32, size.height as f32);

        // Спавним 5 случайных
        let count = 5.min(self.loader.configs.len());
        for i in 0..count {
            let config = &self.loader.configs[i];
            let x = fastrand::f32() * (size.width as f32 - 200.0) + 100.0;
            let y = fastrand::f32() * (size.height as f32 - 200.0) + 100.0;

            let id = self.world.next_id;
            self.world.next_id += 1;
            let mut pony = PonyEntity::new_sprite(id, Vec2::new(x, y), tex_id, 1, 0.1);
            pony.velocity = Vec2::new(
                (fastrand::f32() - 0.5) * 100.0,
                (fastrand::f32() - 0.5) * 60.0,
            );
            if let Some(beh) = config.behaviors.first() {
                pony.current_animation = beh.name.clone();
            }
            self.world.ponies.insert(id, pony);
            println!("  spawned: {} at ({:.0}, {:.0})", config.name, x, y);
        }

        window.set_visible(true);
        self.window = Some(window);
        self.renderer = Some(renderer);
        self.last_frame = Some(std::time::Instant::now());
        println!("PonyWindow: ready!");
    }

    pub fn update_and_render(&mut self) {
        if let (Some(renderer), Some(window)) = (&mut self.renderer, &self.window) {
            let now = std::time::Instant::now();
            let dt = self.last_frame
                .map(|f| (now - f).as_secs_f32().min(0.05))
                .unwrap_or(0.016);
            self.last_frame = Some(now);

            self.world.update(dt);

            let ponies: Vec<&PonyEntity> = self.world.ponies.values().collect();
            if !ponies.is_empty() {
                match renderer.render(&ponies) {
                    Ok(_) => {},
                    Err(wgpu::SurfaceError::Outdated) => {
                        // Surface outdated — пересоздаём
                        let size = window.inner_size();
                        renderer.resize((size.width, size.height));
                    }
                    Err(e) => eprintln!("Render error: {:?}", e),
                }
            }
        }
    }

    pub fn spawn_pony(&mut self, name: &str) -> u64 {
        let id = self.world.next_id;
        self.world.next_id += 1;

        let tex_id = 0; // fallback

        let x = fastrand::f32() * (self.world.screen_size.0 - 200.0) + 100.0;
        let y = fastrand::f32() * (self.world.screen_size.1 - 200.0) + 100.0;

        let mut pony = PonyEntity::new_sprite(id, Vec2::new(x, y), tex_id, 1, 0.1);
        pony.velocity = Vec2::new(
            (fastrand::f32() - 0.5) * 100.0,
            (fastrand::f32() - 0.5) * 60.0,
        );

        if let Some(config) = self.loader.configs.iter().find(|c| c.name == name) {
            if let Some(beh) = config.behaviors.first() {
                pony.current_animation = beh.name.clone();
            }
        }

        self.world.ponies.insert(id, pony);
        println!("Spawned '{}' (id={})", name, id);
        id
    }
}

fn create_white_png() -> Vec<u8> {
    vec![
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x02,
        0x08, 0x06, 0x00, 0x00, 0x00, 0x00, 0x2E, 0xBE,
        0x98, 0x1B, 0x00, 0x00, 0x00, 0x14, 0x49, 0x44,
        0x41, 0x54, 0x78, 0x9C, 0x62, 0x60, 0x60, 0x60,
        0xF8, 0x0F, 0x00, 0x01, 0x01, 0x00, 0x02, 0x02,
        0x02, 0xFE, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
        0xFF, 0xFF, 0x07, 0x80, 0x00, 0x15, 0x01, 0x5D,
        0xB8, 0xDA, 0x22, 0x00, 0x00, 0x00, 0x00, 0x49,
        0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82,
    ]
}