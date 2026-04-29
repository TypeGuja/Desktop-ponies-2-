// src_rust/window_manager.rs (исправленный)
use std::sync::Arc;
use winit::{
    event_loop::{ActiveEventLoop, EventLoop},
    window::Window,
};
use winit::application::ApplicationHandler;

use crate::renderer::Renderer;
use crate::world::World;
use crate::loader::DesktopPoniesLoader;
use crate::pony_factory::PonyFactory;
use crate::pony::PonyEntity;
use glam::Vec2;

#[derive(Clone, Debug)]
pub struct PonyInfo {
    pub id: u64,
    pub name: String,
    pub x: f32,
    pub y: f32,
    pub animation: String,
    pub is_skeletal: bool,
}

pub enum WindowMode {
    Manager,
    Ponies {
        window: Arc<Window>,
        renderer: Renderer,
        world: World,
    },
    None,
}

pub struct PonyWindow {
    pub mode: WindowMode,
    pub factory: PonyFactory,
    pub loader: DesktopPoniesLoader,
    pub last_frame: Option<std::time::Instant>,
}

impl PonyWindow {
    pub fn new() -> Self {
        Self {
            mode: WindowMode::None,
            factory: PonyFactory::new(),
            loader: DesktopPoniesLoader::new("."),
            last_frame: None,
        }
    }

    pub fn run(mut self) {
        let event_loop = EventLoop::new().unwrap();
        event_loop.run_app(&mut self).unwrap();
    }

    /// Инициализация окна пони (вызывается в ApplicationHandler::resumed)
    fn init_pony_window(&mut self, active_loop: &ActiveEventLoop) {
        let window = Arc::new(
            active_loop
                .create_window(
                    Window::default_attributes()
                        .with_title("Desktop Ponies")
                        .with_decorations(false)
                        .with_transparent(true),
                )
                .unwrap(),
        );

        let mut renderer = pollster::block_on(Renderer::new(window.clone()));
        let mut world = World::new(1920.0, 1080.0);

        // Загружаем оригинальных пони
        if let Err(e) = self.loader.load_all() {
            eprintln!("Loader warning: {}", e);
        }

        // Тестовые пони
        let white_png = create_white_png();
        let tex_id = renderer.texture_manager.load_texture(
            &renderer.device,
            &renderer.queue,
            "fallback",
            &white_png,
            1,
        );
        world.spawn_sprite_pony(Vec2::new(200.0, 200.0), tex_id, 1, 10.0);
        world.spawn_sprite_pony(Vec2::new(500.0, 150.0), tex_id, 1, 10.0);
        world.spawn_skeletal_pony(Vec2::new(800.0, 300.0));

        self.mode = WindowMode::Ponies { window, renderer, world };
        self.last_frame = Some(std::time::Instant::now());
    }

    // --- Публичные методы для Tauri ---

    pub fn initialize(&mut self) {
        // Публичный метод-заглушка, реальная инициализация в resumed()
    }

    pub fn spawn_skeletal_pony(&mut self, _name: String, position: Vec2, _body: [f32; 3], _mane: [f32; 3]) -> u64 {
        if let WindowMode::Ponies { world, .. } = &mut self.mode {
            world.spawn_skeletal_pony(position)
        } else { 0 }
    }

    pub fn spawn_sprite_pony(&mut self, _name: String, _behavior: String, position: Vec2) -> Option<u64> {
        if let WindowMode::Ponies { world, .. } = &mut self.mode {
            let id = world.next_id;
            world.next_id += 1;
            world.ponies.insert(id, PonyEntity::new_sprite(id, position, 0, 1, 0.1));
            Some(id)
        } else { None }
    }

    pub fn remove_pony(&mut self, id: u64) {
        if let WindowMode::Ponies { world, .. } = &mut self.mode {
            world.ponies.remove(&id);
        }
    }

    pub fn remove_all_ponies(&mut self) {
        if let WindowMode::Ponies { world, .. } = &mut self.mode {
            world.ponies.clear();
        }
    }

    pub fn set_pony_animation(&mut self, id: u64, animation: &str) {
        if let WindowMode::Ponies { world, .. } = &mut self.mode {
            if let Some(pony) = world.ponies.get_mut(&id) {
                pony.current_animation = animation.to_string();
                pony.animation_time = 0.0;
            }
        }
    }

    pub fn get_pony_list(&self) -> Vec<PonyInfo> {
        if let WindowMode::Ponies { world, .. } = &self.mode {
            world.ponies.values().map(|p| PonyInfo {
                id: p.id, name: format!("Pony {}", p.id),
                x: p.position.x, y: p.position.y,
                animation: p.current_animation.clone(),
                is_skeletal: p.is_skeletal(),
            }).collect()
        } else { vec![] }
    }

    pub fn start_conga(&mut self, leader_id: u64) {
        if let WindowMode::Ponies { world, .. } = &mut self.mode {
            for pony in world.ponies.values_mut() {
                if pony.id != leader_id {
                    pony.current_animation = "conga".to_string();
                    pony.animation_time = fastrand::f32() * 2.0;
                }
            }
        }
    }

    pub fn update(&mut self, dt: f32) {
        if let WindowMode::Ponies { world, .. } = &mut self.mode {
            world.update(dt);
        }
    }

    pub fn render(&mut self) -> Result<(), wgpu::SurfaceError> {
        if let WindowMode::Ponies { world, renderer, .. } = &mut self.mode {
            let ponies: Vec<&PonyEntity> = world.ponies.values().collect();
            renderer.render(&ponies)
        } else { Ok(()) }
    }
}

impl ApplicationHandler for PonyWindow {
    fn resumed(&mut self, active_loop: &ActiveEventLoop) {
        if matches!(self.mode, WindowMode::None) {
            self.init_pony_window(active_loop);
        }
    }

    fn window_event(&mut self, active_loop: &ActiveEventLoop, _id: winit::window::WindowId, event: winit::event::WindowEvent) {
        if let WindowMode::Ponies { renderer, world, .. } = &mut self.mode {
            match event {
                winit::event::WindowEvent::CloseRequested => active_loop.exit(),
                winit::event::WindowEvent::Resized(size) => {
                    renderer.resize((size.width, size.height));
                    world.screen_size = (size.width as f32, size.height as f32);
                }
                _ => {}
            }
        }
    }

    fn about_to_wait(&mut self, _loop: &ActiveEventLoop) {
        if let WindowMode::Ponies { window, renderer, world, .. } = &mut self.mode {
            let now = std::time::Instant::now();
            let dt = self.last_frame.map(|f| (now - f).as_secs_f32().min(0.05)).unwrap_or(0.016);
            self.last_frame = Some(now);

            world.update(dt);
            if let Ok(_) = renderer.render(&world.ponies.values().collect::<Vec<_>>()) {
                window.request_redraw();
            }
        }
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