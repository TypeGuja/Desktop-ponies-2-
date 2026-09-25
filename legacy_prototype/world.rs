// src_rust/world.rs
// src_rust/world.rs
// src_rust/world.rs
use glam::Vec2;
use crate::pony::PonyEntity;
use std::collections::HashMap;

pub struct World {
    pub ponies: HashMap<u64, PonyEntity>,
    pub next_id: u64,
    pub screen_size: (f32, f32),
}

impl World {
    pub fn new(screen_width: f32, screen_height: f32) -> Self {
        Self {
            ponies: HashMap::new(),
            next_id: 0,
            screen_size: (screen_width, screen_height),
        }
    }

    pub fn spawn_skeletal_pony(&mut self, position: Vec2) -> u64 {
        let id = self.next_id;
        self.next_id += 1;

        let mut pony = PonyEntity::new_skeletal(id, position);
        pony.velocity = Vec2::new(
            rand_signed() * 40.0,
            rand_signed() * 30.0,
        );

        self.ponies.insert(id, pony);
        id
    }

    pub fn spawn_sprite_pony(&mut self, position: Vec2, texture_id: usize, frame_count: u32, fps: f32) -> u64 {
        let id = self.next_id;
        self.next_id += 1;

        let mut pony = PonyEntity::new_sprite(id, position, texture_id, frame_count, 1.0 / fps);
        pony.velocity = Vec2::new(
            rand_signed() * 40.0,
            rand_signed() * 30.0,
        );

        self.ponies.insert(id, pony);
        id
    }

    pub fn update(&mut self, dt: f32) {
        let (w, h) = self.screen_size;
        for pony in self.ponies.values_mut() {
            pony.update(dt, w, h);
        }
    }

    pub fn skeletal_count(&self) -> usize {
        self.ponies.values().filter(|p| p.is_skeletal()).count()
    }

    pub fn sprite_count(&self) -> usize {
        self.ponies.values().filter(|p| !p.is_skeletal()).count()
    }
}

fn rand_signed() -> f32 {
    (fastrand::f32() - 0.5) * 2.0
}