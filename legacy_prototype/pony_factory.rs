// src_rust/pony_factory.rs (исправленный)
use glam::Vec2;
use std::collections::HashMap;
use crate::loader::PonyConfig;
use crate::pony::{PonyEntity, SkeletalVisuals};

pub struct PonyFactory {
    next_id: u64,
}

impl PonyFactory {
    pub fn new() -> Self {
        Self { next_id: 0 }
    }

    pub fn create_skeletal(
        &mut self,
        _config: &PonyConfig,
        position: Vec2,
        texture_atlas_id: usize,
        body_color: [f32; 3],
        mane_color: [f32; 3],
        eye_color: [f32; 3],
    ) -> PonyEntity {
        let id = self.next_id;
        self.next_id += 1;

        let visuals = SkeletalVisuals {
            texture_atlas_id,
            body_color,
            mane_color,
            tail_color: mane_color,
            eye_color,
            cutie_mark_texture_id: None,
        };

        PonyEntity::new_skeletal_with_visuals(id, position, visuals)
    }

    pub fn create_sprite_from_behavior(
        &mut self,
        config: &PonyConfig,
        behavior_name: &str,
        texture_map: &HashMap<String, (usize, u32)>,
        position: Vec2,
    ) -> Option<PonyEntity> {
        let behavior = config.behaviors.iter().find(|b| b.name == behavior_name)?;

        let sprite_name = if !behavior.sprite_right.is_empty() {
            &behavior.sprite_right
        } else if !behavior.sprite_left.is_empty() {
            &behavior.sprite_left
        } else {
            return None;
        };

        let (tex_id, frame_count) = texture_map.get(sprite_name)?;

        let id = self.next_id;
        self.next_id += 1;

        // ИСПРАВЛЕНО: было duration_right, стало max_duration
        let frame_duration = if *frame_count > 0 {
            behavior.max_duration / *frame_count as f32
        } else {
            0.1
        };

        let mut pony = PonyEntity::new_sprite(
            id, position, *tex_id, *frame_count, frame_duration,
        );

        pony.current_animation = behavior_name.to_string();
        pony.velocity = Vec2::new(
            behavior.speed * 50.0 * if fastrand::bool() { 1.0 } else { -1.0 },
            behavior.speed * 30.0 * if fastrand::bool() { 1.0 } else { -1.0 },
        );

        Some(pony)
    }

    pub fn create_default_sprite(
        &mut self,
        config: &PonyConfig,
        texture_map: &HashMap<String, (usize, u32)>,
        position: Vec2,
    ) -> Option<PonyEntity> {
        for behavior in &config.behaviors {
            if !behavior.sprite_right.is_empty() || !behavior.sprite_left.is_empty() {
                return self.create_sprite_from_behavior(config, &behavior.name, texture_map, position);
            }
        }
        None
    }
}