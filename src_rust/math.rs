// src_rust/math.rs
use glam::{Vec2, Vec3, Mat4, Quat};

pub const PI: f32 = std::f32::consts::PI;

pub fn lerp(a: f32, b: f32, t: f32) -> f32 {
    a + (b - a) * t.clamp(0.0, 1.0)
}

pub fn vec2_lerp(a: Vec2, b: Vec2, t: f32) -> Vec2 {
    Vec2::new(lerp(a.x, b.x, t), lerp(a.y, b.y, t))
}

pub fn quat_slerp(a: Quat, b: Quat, t: f32) -> Quat {
    a.slerp(b, t.clamp(0.0, 1.0))
}