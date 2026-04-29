// src_rust/pose_generator.rs
use glam::Quat;
use crate::skeleton::Skeleton;

pub struct PoseGenerator;

impl PoseGenerator {
    /// Idle: пони стоит, слегка покачивается
    pub fn apply_idle(skeleton: &mut Skeleton, time: f32) {
        let sway = (time * 1.5).sin() * 0.02;
        let breathe = (time * 2.0).sin() * 0.03;

        skeleton.set_bone_rotation("body", Quat::from_rotation_z(sway));
        skeleton.set_bone_rotation("head", Quat::from_rotation_x(breathe));

        let ear_twitch = (time * 3.7).sin() * 0.1;
        skeleton.set_bone_rotation("ear_left", Quat::from_rotation_z(0.2 + ear_twitch));
        skeleton.set_bone_rotation("ear_right", Quat::from_rotation_z(-0.2 - ear_twitch * 0.7));

        skeleton.set_bone_rotation("front_left_upper", Quat::from_rotation_z(0.1));
        skeleton.set_bone_rotation("front_left_lower", Quat::from_rotation_z(0.05));
        skeleton.set_bone_rotation("front_right_upper", Quat::from_rotation_z(-0.1));
        skeleton.set_bone_rotation("front_right_lower", Quat::from_rotation_z(-0.05));
        skeleton.set_bone_rotation("back_left_upper", Quat::from_rotation_z(-0.15));
        skeleton.set_bone_rotation("back_left_lower", Quat::from_rotation_z(-0.05));
        skeleton.set_bone_rotation("back_right_upper", Quat::from_rotation_z(0.15));
        skeleton.set_bone_rotation("back_right_lower", Quat::from_rotation_z(0.05));
    }

    /// Walk: пони идёт шагом
    pub fn apply_walk(skeleton: &mut Skeleton, time: f32, speed: f32) {
        let cycle = time * speed * 5.0;
        let lean = 0.15;

        skeleton.set_bone_rotation("body", Quat::from_rotation_z(lean));

        let fl_angle = cycle.sin() * 0.5;
        skeleton.set_bone_rotation("front_left_upper", Quat::from_rotation_z(fl_angle));
        skeleton.set_bone_rotation("front_left_lower", Quat::from_rotation_z(fl_angle.abs() * 0.3));

        let fr_angle = (cycle + std::f32::consts::PI).sin() * 0.5;
        skeleton.set_bone_rotation("front_right_upper", Quat::from_rotation_z(fr_angle));
        skeleton.set_bone_rotation("front_right_lower", Quat::from_rotation_z(fr_angle.abs() * 0.3));

        let bl_angle = (cycle + std::f32::consts::FRAC_PI_2).sin() * 0.45;
        skeleton.set_bone_rotation("back_left_upper", Quat::from_rotation_z(bl_angle));
        skeleton.set_bone_rotation("back_left_lower", Quat::from_rotation_z(bl_angle.abs() * 0.25));

        let br_angle = (cycle + std::f32::consts::PI + std::f32::consts::FRAC_PI_2).sin() * 0.45;
        skeleton.set_bone_rotation("back_right_upper", Quat::from_rotation_z(br_angle));
        skeleton.set_bone_rotation("back_right_lower", Quat::from_rotation_z(br_angle.abs() * 0.25));

        let head_bob = (cycle * 2.0).sin() * 0.04;
        skeleton.set_bone_rotation("head", Quat::from_rotation_x(head_bob));
    }

    /// Gallop: быстрый бег
    pub fn apply_gallop(skeleton: &mut Skeleton, time: f32, speed: f32) {
        let cycle = time * speed * 8.0;
        let lean = 0.3;

        skeleton.set_bone_rotation("body", Quat::from_rotation_z(lean));

        let front_angle = cycle.sin() * 0.6;
        skeleton.set_bone_rotation("front_left_upper", Quat::from_rotation_z(front_angle));
        skeleton.set_bone_rotation("front_right_upper", Quat::from_rotation_z(front_angle));
        skeleton.set_bone_rotation("front_left_lower", Quat::from_rotation_z(front_angle.abs() * 0.4));
        skeleton.set_bone_rotation("front_right_lower", Quat::from_rotation_z(front_angle.abs() * 0.4));

        let back_angle = (cycle + std::f32::consts::PI).sin() * 0.55;
        skeleton.set_bone_rotation("back_left_upper", Quat::from_rotation_z(back_angle));
        skeleton.set_bone_rotation("back_right_upper", Quat::from_rotation_z(back_angle));
        skeleton.set_bone_rotation("back_left_lower", Quat::from_rotation_z(back_angle.abs() * 0.35));
        skeleton.set_bone_rotation("back_right_lower", Quat::from_rotation_z(back_angle.abs() * 0.35));

        skeleton.set_bone_rotation("head", Quat::from_rotation_x((cycle * 2.0).sin() * 0.08));
    }

    /// Sleep: спит лёжа
    pub fn apply_sleep(skeleton: &mut Skeleton, _time: f32) {
        skeleton.set_bone_rotation("body", Quat::from_rotation_z(-std::f32::consts::FRAC_PI_2));
        skeleton.set_bone_rotation("front_left_upper", Quat::from_rotation_z(-1.2));
        skeleton.set_bone_rotation("front_left_lower", Quat::from_rotation_z(-0.8));
        skeleton.set_bone_rotation("front_right_upper", Quat::from_rotation_z(-1.2));
        skeleton.set_bone_rotation("front_right_lower", Quat::from_rotation_z(-0.8));
        skeleton.set_bone_rotation("back_left_upper", Quat::from_rotation_z(-1.0));
        skeleton.set_bone_rotation("back_left_lower", Quat::from_rotation_z(-0.6));
        skeleton.set_bone_rotation("back_right_upper", Quat::from_rotation_z(-1.0));
        skeleton.set_bone_rotation("back_right_lower", Quat::from_rotation_z(-0.6));
        skeleton.set_bone_rotation("head", Quat::from_rotation_x(0.5));
    }

    /// Buck: брыкание задними ногами
    pub fn apply_buck(skeleton: &mut Skeleton, time: f32) {
        let phase = (time * 3.0).min(1.0);

        if phase < 0.3 {
            let t = phase / 0.3;
            skeleton.set_bone_rotation("body", Quat::from_rotation_z(0.2 * t));
            skeleton.set_bone_rotation("front_left_upper", Quat::from_rotation_z(0.3 * t));
            skeleton.set_bone_rotation("front_right_upper", Quat::from_rotation_z(-0.3 * t));
            skeleton.set_bone_rotation("back_left_upper", Quat::from_rotation_z(0.5 * t));
            skeleton.set_bone_rotation("back_right_upper", Quat::from_rotation_z(-0.5 * t));
        } else if phase < 0.5 {
            let t = (phase - 0.3) / 0.2;
            skeleton.set_bone_rotation("body", Quat::from_rotation_z(-0.5 * t));
            skeleton.set_bone_rotation("back_left_upper", Quat::from_rotation_z(-1.5 * t));
            skeleton.set_bone_rotation("back_right_upper", Quat::from_rotation_z(-1.5 * t));
            skeleton.set_bone_rotation("back_left_lower", Quat::from_rotation_z(-1.0 * t));
            skeleton.set_bone_rotation("back_right_lower", Quat::from_rotation_z(-1.0 * t));
        } else {
            let t = (phase - 0.5) / 0.5;
            let ease = 1.0 - (1.0 - t) * (1.0 - t);
            skeleton.set_bone_rotation("body", Quat::from_rotation_z(-0.5 * (1.0 - ease)));
            skeleton.set_bone_rotation("back_left_upper", Quat::from_rotation_z(-1.5 * (1.0 - ease)));
            skeleton.set_bone_rotation("back_right_upper", Quat::from_rotation_z(-1.5 * (1.0 - ease)));
            skeleton.set_bone_rotation("back_left_lower", Quat::from_rotation_z(-1.0 * (1.0 - ease)));
            skeleton.set_bone_rotation("back_right_lower", Quat::from_rotation_z(-1.0 * (1.0 - ease)));
        }
    }

    /// Rear: вставание на дыбы
    pub fn apply_rear(skeleton: &mut Skeleton, time: f32) {
        let phase = (time * 2.0).min(1.0);
        let body_rot = phase * 1.2;

        skeleton.set_bone_rotation("body", Quat::from_rotation_z(body_rot));
        skeleton.set_bone_rotation("front_left_upper", Quat::from_rotation_z(-0.8 * phase));
        skeleton.set_bone_rotation("front_right_upper", Quat::from_rotation_z(-0.8 * phase));
        skeleton.set_bone_rotation("front_left_lower", Quat::from_rotation_z(-0.4 * phase));
        skeleton.set_bone_rotation("front_right_lower", Quat::from_rotation_z(-0.4 * phase));
        skeleton.set_bone_rotation("back_left_upper", Quat::from_rotation_z(-0.3 * phase));
        skeleton.set_bone_rotation("back_right_upper", Quat::from_rotation_z(-0.3 * phase));
        skeleton.set_bone_rotation("head", Quat::from_rotation_x(-0.5 * phase));
    }

    /// Pose: гордая поза
    pub fn apply_pose(skeleton: &mut Skeleton, time: f32) {
        let t = (time * 0.5).sin().abs();

        skeleton.set_bone_rotation("body", Quat::from_rotation_z(-0.15));
        skeleton.set_bone_rotation("head", Quat::from_rotation_x(-0.3 + t * 0.1));
        skeleton.set_bone_rotation("front_left_upper", Quat::from_rotation_z(0.3));
        skeleton.set_bone_rotation("front_right_upper", Quat::from_rotation_z(-0.1));
        skeleton.set_bone_rotation("back_left_upper", Quat::from_rotation_z(-0.2));
        skeleton.set_bone_rotation("back_right_upper", Quat::from_rotation_z(0.3));
        skeleton.set_bone_rotation("ear_left", Quat::from_rotation_z(0.3));
        skeleton.set_bone_rotation("ear_right", Quat::from_rotation_z(-0.3));
    }

    /// Conga: танец конга
    pub fn apply_conga(skeleton: &mut Skeleton, time: f32) {
        let kick_cycle = (time * 4.0).sin();

        skeleton.set_bone_rotation("body", Quat::from_rotation_z(0.15));
        skeleton.set_bone_rotation("front_left_upper", Quat::from_rotation_z(if kick_cycle > 0.0 { 0.6 } else { 0.1 }));
        skeleton.set_bone_rotation("front_right_upper", Quat::from_rotation_z(if kick_cycle < 0.0 { -0.6 } else { -0.1 }));
        skeleton.set_bone_rotation("head", Quat::from_rotation_x(kick_cycle.abs() * 0.15));
    }
}