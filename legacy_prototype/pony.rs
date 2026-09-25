// src_rust/pony.rs (добавить в конец, перед impl PonyEntity)
// src_rust/pony.rs
use glam::{Vec2, Vec3, Quat};
use crate::skeleton::Skeleton;
use crate::animation::AnimationClip;
use crate::verlet::VerletChain;
use crate::loader::MovementType;
use std::collections::HashMap;

pub struct SkeletalVisuals {
    pub texture_atlas_id: usize,
    pub body_color: [f32; 3],
    pub mane_color: [f32; 3],
    pub tail_color: [f32; 3],
    pub eye_color: [f32; 3],
    pub cutie_mark_texture_id: Option<usize>,
}

pub enum PonyRenderType {
    Skeletal {
        skeleton: Skeleton,
        animations: HashMap<String, AnimationClip>,
        tail_chain: VerletChain,
        mane_chain: VerletChain,
        visuals: Option<SkeletalVisuals>,
    },
    Sprite {
        texture_id: usize,
        frame_count: u32,
        current_frame: u32,
        frame_time: f32,
        frame_duration: f32,
    },
}

pub struct PonyEntity {
    pub id: u64,
    pub position: Vec2,
    pub velocity: Vec2,
    pub facing_right: bool,
    pub render_type: PonyRenderType,
    pub current_animation: String,
    pub animation_time: f32,
    pub scale: f32,
    pub speed_override: Option<f32>,
    pub movement_type: Option<MovementType>,
    pub grabbed: bool,
}

impl PonyEntity {
    pub fn new_skeletal(id: u64, position: Vec2) -> Self {
        let skeleton = Skeleton::create_pony_skeleton();
        let mut animations = HashMap::new();
        animations.insert("walk".into(), AnimationClip::create_walk());
        animations.insert("idle".into(), AnimationClip::create_idle());

        let tail_chain = VerletChain::new(Vec2::new(position.x, position.y - 55.0), 6, 9.0);
        let mane_chain = VerletChain::new(Vec2::new(position.x, position.y + 18.0), 4, 7.0);

        Self {
            id,
            position,
            velocity: Vec2::ZERO,
            facing_right: true,
            render_type: PonyRenderType::Skeletal {
                skeleton,
                animations,
                tail_chain,
                mane_chain,
                visuals: None,
            },
            current_animation: "idle".to_string(),
            animation_time: 0.0,
            scale: 1.0,
            speed_override: None,
            movement_type: None,
            grabbed: false,
        }
    }

    pub fn new_skeletal_with_visuals(id: u64, position: Vec2, vis: SkeletalVisuals) -> Self {
        let mut pony = Self::new_skeletal(id, position);
        if let PonyRenderType::Skeletal { visuals, .. } = &mut pony.render_type {
            *visuals = Some(vis);
        }
        pony
    }

    pub fn new_sprite(id: u64, position: Vec2, texture_id: usize, frame_count: u32, frame_duration: f32) -> Self {
        Self {
            id,
            position,
            velocity: Vec2::ZERO,
            facing_right: true,
            render_type: PonyRenderType::Sprite {
                texture_id,
                frame_count,
                current_frame: 0,
                frame_time: 0.0,
                frame_duration,
            },
            current_animation: "walk".to_string(),
            animation_time: 0.0,
            scale: 1.0,
            speed_override: None,
            movement_type: None,
            grabbed: false,
        }
    }

    pub fn update(&mut self, dt: f32, screen_width: f32, screen_height: f32) {
        self.position += self.velocity * dt;

        let margin = 50.0;
        if self.position.x < margin {
            self.position.x = margin;
            self.velocity.x = self.velocity.x.abs();
            self.facing_right = true;
        } else if self.position.x > screen_width - margin {
            self.position.x = screen_width - margin;
            self.velocity.x = -self.velocity.x.abs();
            self.facing_right = false;
        }
        if self.position.y < margin {
            self.position.y = margin;
            self.velocity.y = self.velocity.y.abs();
        } else if self.position.y > screen_height - margin {
            self.position.y = screen_height - margin;
            self.velocity.y = -self.velocity.y.abs();
        }

        if self.velocity.x > 1.0 {
            self.facing_right = true;
        } else if self.velocity.x < -1.0 {
            self.facing_right = false;
        }

        let speed = self.velocity.length();
        self.current_animation = if speed > 5.0 { "walk".to_string() } else { "idle".to_string() };

        self.animation_time += dt;

        match &mut self.render_type {
            PonyRenderType::Skeletal { skeleton, animations, tail_chain, mane_chain, .. } => {
                if let Some(clip) = animations.get(&self.current_animation) {
                    let pose = clip.sample(self.animation_time);
                    for (bone_name, rotation) in &pose {
                        skeleton.set_bone_rotation(bone_name, *rotation);
                    }
                    if !clip.looped && self.animation_time >= clip.duration {
                        self.animation_time = 0.0;
                    }
                }

                skeleton.local_poses[0] = glam::Mat4::from_translation(Vec3::new(
                    self.position.x,
                    self.position.y,
                    0.0,
                ));

                if !self.facing_right {
                    skeleton.local_poses[0] = skeleton.local_poses[0] * glam::Mat4::from_scale(Vec3::new(-1.0, 1.0, 1.0));
                }

                skeleton.update_global_poses();

                if let Some(tail_base) = skeleton.get_bone_world_position("body") {
                    let anchor = Vec2::new(tail_base.x, tail_base.y - 55.0);
                    let anchor_vel = self.velocity;
                    tail_chain.update(dt, Vec2::new(0.0, -600.0), anchor, anchor_vel);

                    let angles = tail_chain.get_angles_relative_to_vertical();
                    for (i, angle) in angles.iter().enumerate() {
                        let bone_name = format!("tail_{}", i);
                        skeleton.set_bone_rotation(&bone_name, Quat::from_rotation_z(*angle));
                    }
                }

                if let Some(mane_base) = skeleton.get_bone_world_position("head") {
                    let anchor = Vec2::new(mane_base.x, mane_base.y + 18.0);
                    let anchor_vel = self.velocity;
                    mane_chain.update(dt, Vec2::new(0.0, -300.0), anchor, anchor_vel);

                    let angles = mane_chain.get_angles_relative_to_vertical();
                    for (i, angle) in angles.iter().enumerate() {
                        let bone_name = format!("mane_{}", i);
                        skeleton.set_bone_rotation(&bone_name, Quat::from_rotation_z(*angle));
                    }
                }

                skeleton.update_global_poses();
            }
            PonyRenderType::Sprite { frame_count, current_frame, frame_time, frame_duration, .. } => {
                *frame_time += dt;
                if *frame_time >= *frame_duration {
                    *frame_time -= *frame_duration;
                    *current_frame = (*current_frame + 1) % *frame_count;
                }
            }
        }
    }

    pub fn is_skeletal(&self) -> bool {
        matches!(self.render_type, PonyRenderType::Skeletal { .. })
    }
}